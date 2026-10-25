"""
ServeLocal RAG (Retrieval-Augmented Generation) Engine
------------------------------------------------------
A production-ready RAG system designed for the ServeLocal Hyperlocal Marketplace.

Features:
1. Retrieval:
   - Indexes Service Categories, Worker Profiles, Skills, Pricing, and Platform FAQs.
   - Uses Scikit-learn TF-IDF vectorization + Cosine Similarity for fast local search.
   - Intelligent multi-factor ranking (relevance score thresholding).
2. Augmentation:
   - Formats relevant marketplace context, verified workers, and guidelines into grounded prompts.
3. Generation:
   - Supports Google Gemini API (gemini-1.5-flash / gemini-pro)
   - Supports OpenAI API (gpt-4o-mini / gpt-3.5-turbo)
   - Built-in Local Synthesizer: Fully functional offline fallback when no API key is provided.
4. Integration:
   - Flask Blueprint with `/api/rag/query`, `/api/rag/status`, `/api/rag/reindex`
   - Interactive Web Chat Assistant view at `/assistant`
   - Standalone CLI execution (`python rag.py "query"`)
"""

import os
import sys
import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import requests

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Vector retrieval with scikit-learn
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Flask & Blueprint
from flask import Blueprint, request, jsonify, render_template, current_app

logger = logging.getLogger("servelocal.rag")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Document:
    doc_id: str
    doc_type: str  # 'category', 'worker', 'faq', 'policy'
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class SearchResult:
    document: Document
    score: float

    def to_dict(self):
        return {
            "doc_id": self.document.doc_id,
            "doc_type": self.document.doc_type,
            "title": self.document.title,
            "content": self.document.content,
            "score": round(float(self.score), 4),
            "metadata": self.document.metadata,
        }


# ---------------------------------------------------------------------------
# Curated Knowledge Base (FAQs, Policies, Platform Guidelines)
# ---------------------------------------------------------------------------

DEFAULT_FAQS: List[Dict[str, Any]] = [
    {
        "doc_id": "faq_how_booking_works",
        "doc_type": "faq",
        "title": "How Booking Works on ServeLocal",
        "content": (
            "Booking a service on ServeLocal takes 3 simple steps: "
            "1. Post a job request specifying category, address, urgency (immediate, today, or scheduled), and budget. "
            "2. Nearby verified local workers receive your request and submit transparent price offers with arrival estimates. "
            "3. Compare worker offers, ratings, and reviews, then accept the best offer. Once accepted, track the worker's status until completion."
        ),
        "metadata": {"action": "post_job", "url": "/customer/post-job"},
    },
    {
        "doc_id": "faq_pricing_and_fees",
        "doc_type": "faq",
        "title": "Pricing, Quotes, and Brokerage Fees",
        "content": (
            "ServeLocal charges 0% brokerage to customers. All quotes are submitted directly by independent "
            "local professionals (plumbers, electricians, cleaners, carpenters, etc.). Standard visit inspection charges "
            "range between ₹149 to ₹299 depending on the skill, and final prices are agreed before any work begins."
        ),
        "metadata": {"category": "general"},
    },
    {
        "doc_id": "faq_worker_verification",
        "doc_type": "faq",
        "title": "Safety & Worker Background Checks",
        "content": (
            "Every professional on ServeLocal undergoes phone and identity verification. Workers display badges such as "
            "'Verified Pro' with star ratings based on authentic past customer reviews. Customers can view worker profiles, "
            "years of experience, and completed job counts before accepting an offer."
        ),
        "metadata": {"category": "safety"},
    },
    {
        "doc_id": "faq_cancellation_policy",
        "doc_type": "policy",
        "title": "Cancellation and Rescheduling Policy",
        "content": (
            "Customers can cancel a job request for free at any time before accepting an offer. Once an offer is accepted, "
            "free cancellation is permitted as long as the worker has not departed for your premises. You can also message or "
            "coordinate with the assigned worker directly via your dashboard."
        ),
        "metadata": {"category": "policy"},
    },
    {
        "doc_id": "faq_urgent_emergency",
        "doc_type": "faq",
        "title": "Emergency and Urgent Service Requests",
        "content": (
            "For urgent emergencies like major water leaks, short circuits, or broken locks, select the 'Urgent (Next 2 Hours)' "
            "priority when posting your job. This broadcasts an instant high-priority alert to all available active workers within a 10 km radius."
        ),
        "metadata": {"action": "post_job", "urgency": "urgent"},
    },
    {
        "doc_id": "faq_becoming_a_worker",
        "doc_type": "faq",
        "title": "How to Join as a Service Professional / Worker",
        "content": (
            "Independent service providers can join ServeLocal by registering as a 'Partner / Pro'. Simply submit your phone number, "
            "select your primary skill categories, define your service radius in kilometers, and set your weekly availability schedule. "
            "Once approved by the admin team, you can browse incoming customer job requests and submit competitive offers."
        ),
        "metadata": {"action": "register_worker", "url": "/auth/register/worker"},
    },
]


# ---------------------------------------------------------------------------
# Core RAG Knowledge Retriever & Generator
# ---------------------------------------------------------------------------

class ServeLocalRAG:
    """
    Retrieval-Augmented Generation engine for ServeLocal.
    """

    def __init__(self, app=None):
        self.app = app
        self.documents: List[Document] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.doc_vectors = None
        self.is_indexed: bool = False

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        with app.app_context():
            self.build_index()

    def build_index(self) -> int:
        """
        Builds or refreshes the search index from database models and static FAQs.
        """
        docs: List[Document] = []

        # 1. Index Static FAQs and Policies
        for item in DEFAULT_FAQS:
            docs.append(Document(
                doc_id=item["doc_id"],
                doc_type=item["doc_type"],
                title=item["title"],
                content=item["content"],
                metadata=item.get("metadata", {})
            ))

        # 2. Index Dynamic Service Categories from DB
        try:
            from app.models import ServiceCategory, Worker, WorkerSkill, User
            categories = ServiceCategory.query.filter_by(is_active=True).all()
            for cat in categories:
                skills_list = [s.skill_name for s in cat.skills] if cat.skills else []
                skills_summary = ", ".join(set(skills_list)) if skills_list else "General maintenance"
                content = (
                    f"Service Category: {cat.name} (Icon: {cat.icon}). "
                    f"Description: {cat.description}. "
                    f"Common tasks and skills: {skills_summary}."
                )
                docs.append(Document(
                    doc_id=f"cat_{cat.id}",
                    doc_type="category",
                    title=f"Category: {cat.name}",
                    content=content,
                    metadata={
                        "category_id": cat.id,
                        "category_name": cat.name,
                        "icon": cat.icon,
                        "action": "post_job",
                        "url": f"/customer/post-job?category_id={cat.id}",
                    }
                ))

            # 3. Index Active Workers and their skills
            workers = Worker.query.filter_by(is_active=True).all()
            for worker in workers:
                user = worker.user
                if not user or not user.is_active:
                    continue

                skills_info = []
                for s in worker.skills:
                    cat_name = s.category.name if s.category else "General"
                    rate = f" ({s.rate_description})" if s.rate_description else ""
                    skills_info.append(f"{s.skill_name} under {cat_name}{rate}")

                skills_str = "; ".join(skills_info) if skills_info else "General household maintenance"
                rating_str = f"{worker.average_rating} ⭐" if worker.average_rating else "New Professional"
                city_str = worker.city or "Bengaluru"

                content = (
                    f"Verified Worker: {user.full_name}. City: {city_str}. "
                    f"Experience: {worker.experience_years} years. Rating: {rating_str}. "
                    f"Service Radius: {worker.service_radius_km} km. "
                    f"Bio: {worker.bio or 'Experienced local service specialist'}. "
                    f"Skills and Rates: {skills_str}."
                )
                docs.append(Document(
                    doc_id=f"worker_{worker.id}",
                    doc_type="worker",
                    title=f"Worker: {user.full_name} ({city_str})",
                    content=content,
                    metadata={
                        "worker_id": worker.id,
                        "name": user.full_name,
                        "city": city_str,
                        "rating": worker.average_rating,
                        "experience": worker.experience_years,
                        "url": f"/worker/{worker.id}",
                    }
                ))

        except Exception as e:
            logger.warning(f"Database indexing skipped or encountered error (running with static FAQs): {e}")

        # Store documents
        self.documents = docs

        # Compute TF-IDF sparse matrix
        if docs:
            corpus = [f"{d.title} {d.content}" for d in docs]
            self.vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=5000
            )
            self.doc_vectors = self.vectorizer.fit_transform(corpus)
            self.is_indexed = True
            logger.info(f"ServeLocal RAG indexed {len(docs)} documents successfully.")
        else:
            self.is_indexed = False

        return len(docs)

    # -----------------------------------------------------------------------
    # Retrieval Phase
    # -----------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 4, doc_type: Optional[str] = None) -> List[SearchResult]:
        """
        Retrieves the top_k most relevant documents for a given user query.
        """
        if not self.is_indexed or not self.documents or not self.vectorizer:
            self.build_index()

        if not self.documents or not self.vectorizer:
            return []

        # Vectorize query
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.doc_vectors).flatten()

        # Rank indices
        ranked_indices = np.argsort(similarities)[::-1]

        results: List[SearchResult] = []
        for idx in ranked_indices:
            score = float(similarities[idx])
            # Only include documents with meaningful semantic overlap
            if score < 0.04 and len(results) >= 1:
                break
            if score <= 0.005:
                break

            doc = self.documents[idx]
            if doc_type and doc.doc_type != doc_type:
                continue

            results.append(SearchResult(document=doc, score=score))
            if len(results) >= top_k:
                break

        return results

    # -----------------------------------------------------------------------
    # Augmentation Phase
    # -----------------------------------------------------------------------
    def build_prompt_context(self, retrieved: List[SearchResult]) -> str:
        """
        Formats retrieved search results into a clean context block for LLM prompt augmentation.
        """
        if not retrieved:
            return "No specific marketplace documents matched the query."

        context_blocks = []
        for i, res in enumerate(retrieved, start=1):
            doc = res.document
            context_blocks.append(
                f"[Source {i}: {doc.title} (Type: {doc.doc_type})]\n"
                f"{doc.content}"
            )
        return "\n\n".join(context_blocks)

    # -----------------------------------------------------------------------
    # Generation Phase
    # -----------------------------------------------------------------------
    def generate_answer(self, query: str, retrieved: List[SearchResult]) -> Dict[str, Any]:
        """
        Generates an augmented answer using available LLM API (Gemini or OpenAI)
        or falls back gracefully to a smart local extractive synthesizer.
        """
        context_str = self.build_prompt_context(retrieved)

        # 1. Try Google Gemini API
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            try:
                answer = self._call_gemini(query, context_str, gemini_key)
                if answer:
                    return {
                        "answer": answer,
                        "provider": "google-gemini",
                        "sources": [r.to_dict() for r in retrieved],
                        "actions": self._extract_actions(retrieved),
                    }
            except Exception as e:
                logger.warning(f"Gemini API generation failed: {e}")

        # 2. Try OpenAI API
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            try:
                answer = self._call_openai(query, context_str, openai_key)
                if answer:
                    return {
                        "answer": answer,
                        "provider": "openai",
                        "sources": [r.to_dict() for r in retrieved],
                        "actions": self._extract_actions(retrieved),
                    }
            except Exception as e:
                logger.warning(f"OpenAI API generation failed: {e}")

        # 3. Robust Offline Local Synthesizer (Zero-dependency & instant)
        answer = self._synthesize_local_response(query, retrieved)
        return {
            "answer": answer,
            "provider": "local-rag-synthesizer",
            "sources": [r.to_dict() for r in retrieved],
            "actions": self._extract_actions(retrieved),
        }

    # -----------------------------------------------------------------------
    # LLM Integrations
    # -----------------------------------------------------------------------
    def _call_gemini(self, query: str, context: str, api_key: str) -> Optional[str]:
        system_instruction = (
            "You are 'LocalBot', the intelligent AI assistant for ServeLocal (a hyperlocal home services marketplace in India). "
            "Answer user questions accurately and concisely using the provided context. "
            "Help customers find services, understand booking/cancellation procedures, and estimate costs. "
            "Always be polite, warm, and encourage booking verified local pros."
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        prompt = (
            f"{system_instruction}\n\n"
            f"--- RELEVANT MARKETPLACE CONTEXT ---\n{context}\n\n"
            f"--- USER QUERY ---\n{query}\n\n"
            f"Provide a helpful and friendly response in clean markdown:"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return None

    def _call_openai(self, query: str, context: str, api_key: str) -> Optional[str]:
        system_prompt = (
            "You are 'LocalBot', the intelligent AI assistant for ServeLocal (a hyperlocal home services marketplace in India). "
            "Answer user questions accurately and concisely using the provided marketplace context. "
            "Help customers find services, estimate costs, and book verified professionals."
        )
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nUser Question: {query}"}
            ],
            "temperature": 0.3,
            "max_tokens": 400
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        return None

    # -----------------------------------------------------------------------
    # Fallback Synthesizer (Extractive & Rule-Grounded)
    # -----------------------------------------------------------------------
    def _synthesize_local_response(self, query: str, retrieved: List[SearchResult]) -> str:
        """
        Creates a grounded, well-structured answer when an external LLM is not configured.
        """
        if not retrieved or retrieved[0].score < 0.04:
            return (
                "👋 Hello! I'm your **ServeLocal AI Assistant**.\n\n"
                "I couldn't find an exact match for your query, but here is how I can help:\n"
                "• **Available Services:** Plumbing, Electrical, Cleaning, Cooking, Carpentry, Appliance Repair, AC Maintenance.\n"
                "• **Transparent Quotes:** Zero brokerage fees, direct worker estimates.\n"
                "• **Easy Booking:** Post a request in under 60 seconds and receive instant offers.\n\n"
                "Try asking: *'How do I post a plumbing request?'* or *'Who can fix electrical wiring in Bengaluru?'*"
            )

        response_parts = []
        response_parts.append("Here is the relevant information from **ServeLocal**:\n")

        for res in retrieved:
            doc = res.document
            if doc.doc_type == "category":
                icon = doc.metadata.get("icon", "🔧")
                name = doc.metadata.get("category_name", doc.title)
                response_parts.append(f"• **{icon} {name}**: {doc.content}")
            elif doc.doc_type == "worker":
                name = doc.metadata.get("name", "Verified Worker")
                rating = doc.metadata.get("rating")
                rating_str = f"⭐ {rating} / 5" if rating else "⭐ New Pro"
                response_parts.append(f"• **{name}** ({rating_str}): {doc.content}")
            elif doc.doc_type in ("faq", "policy"):
                response_parts.append(f"• **{doc.title}**: {doc.content}")

        if any(r.document.doc_type == "category" for r in retrieved):
            response_parts.append("\n👉 **Next step:** Post a service request to receive quotes directly from available nearby pros.")
        elif any(r.document.doc_type == "worker" for r in retrieved):
            response_parts.append("\n👉 **Next step:** You can view this worker's profile and request an instant quote.")

        return "\n".join(response_parts)

    def _extract_actions(self, retrieved: List[SearchResult]) -> List[Dict[str, str]]:
        actions = []
        seen = set()
        for res in retrieved:
            meta = res.document.metadata
            url = meta.get("url")
            if url and url not in seen:
                seen.add(url)
                title = res.document.title
                if "Category:" in title:
                    label = f"Post {title.replace('Category: ', '')} Job"
                elif "Worker:" in title:
                    label = f"View {meta.get('name', 'Worker')}'s Profile"
                else:
                    label = "Learn More"
                actions.append({"label": label, "url": url})
        return actions[:3]

    # -----------------------------------------------------------------------
    # Main Query Pipeline
    # -----------------------------------------------------------------------
    def query(self, user_query: str, top_k: int = 3, doc_type: Optional[str] = None) -> Dict[str, Any]:
        """
        End-to-end RAG entry point: Retrieve + Augment + Generate.
        """
        user_query = user_query.strip()
        if not user_query:
            return {
                "answer": "Please ask a question about our services, local workers, or booking process.",
                "sources": [],
                "actions": [],
                "provider": "none"
            }

        retrieved = self.retrieve(user_query, top_k=top_k, doc_type=doc_type)
        return self.generate_answer(user_query, retrieved)


# ---------------------------------------------------------------------------
# Global Singleton & Flask Blueprint
# ---------------------------------------------------------------------------

rag_engine = ServeLocalRAG()
rag_bp = Blueprint("rag", __name__)


@rag_bp.route("/assistant", methods=["GET"])
def assistant_page():
    """
    Renders the dedicated modern AI Assistant chat page.
    """
    return render_template("main/assistant.html")


@rag_bp.route("/api/rag/query", methods=["POST"])
def api_query():
    """
    JSON API endpoint for RAG queries.
    Payload: {"query": "how do I book a plumber", "top_k": 3}
    """
    data = request.get_json(silent=True) or {}
    user_query = data.get("query", "").strip()
    top_k = int(data.get("top_k", 3))
    doc_type = data.get("doc_type")

    if not user_query:
        return jsonify({"error": "Query string is required"}), 400

    result = rag_engine.query(user_query, top_k=top_k, doc_type=doc_type)
    return jsonify(result)


@rag_bp.route("/api/rag/status", methods=["GET"])
def api_status():
    """
    Returns indexing and engine status.
    """
    return jsonify({
        "status": "ready" if rag_engine.is_indexed else "indexing_needed",
        "total_documents": len(rag_engine.documents),
        "gemini_enabled": bool(os.environ.get("GEMINI_API_KEY")),
        "openai_enabled": bool(os.environ.get("OPENAI_API_KEY")),
        "sample_topics": [d.title for d in rag_engine.documents[:5]]
    })


@rag_bp.route("/api/rag/reindex", methods=["POST"])
def api_reindex():
    """
    Forces a rebuild of the RAG index from current database state.
    """
    count = rag_engine.build_index()
    return jsonify({"message": f"Successfully re-indexed {count} documents.", "count": count})


# ---------------------------------------------------------------------------
# CLI & Standalone Test Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("⚡ ServeLocal RAG (Retrieval-Augmented Generation) Engine")
    print("=" * 60)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            rag = ServeLocalRAG(app)
    except Exception as err:
        print(f"[Notice] Running standalone without Flask app context: {err}")
        rag = ServeLocalRAG()
        rag.build_index()

    print(f"\nIndexed {len(rag.documents)} documents.")

    sample_query = sys.argv[1] if len(sys.argv) > 1 else "My kitchen tap is leaking, how can I get a plumber?"
    print(f"\n[Query]: {sample_query}\n")

    res = rag.query(sample_query)
    print(f"[Provider]: {res['provider']}")
    print("-" * 50)
    print(f"[Answer]:\n{res['answer']}")
    print("-" * 50)
    print(f"[Retrieved Sources ({len(res['sources'])})]:")
    for s in res['sources']:
        print(f"  • {s['title']} (score: {s['score']})")
    if res['actions']:
        print(f"[Actions]: {res['actions']}")
    print("=" * 60)
