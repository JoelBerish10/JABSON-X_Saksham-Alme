"""
ServeLocal RAG Entry Point & CLI
---------------------------------
Run directly:
    python rag.py "How much does electrical wiring cost?"
    python rag.py --interactive
    python rag.py --reindex
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app
from app.rag import ServeLocalRAG, rag_engine


def main():
    app = create_app()
    with app.app_context():
        rag_engine.build_index()

        args = sys.argv[1:]
        if not args:
            query_text = "I need an urgent plumber for a leaking pipe in Bengaluru. How do I book?"
        elif args[0] in ("-i", "--interactive"):
            print("=" * 60)
            print("🤖 ServeLocal AI Assistant Interactive Console (Type 'exit' to quit)")
            print("=" * 60)
            while True:
                try:
                    q = input("\nYou: ").strip()
                    if not q or q.lower() in ("exit", "quit", "q"):
                        break
                    res = rag_engine.query(q)
                    print(f"\n[AI Assistant ({res['provider']})]:\n{res['answer']}")
                    if res.get("actions"):
                        print(f"\nRecommended Actions: {', '.join(a['label'] for a in res['actions'])}")
                except (KeyboardInterrupt, EOFError):
                    break
            print("\nGoodbye!")
            return
        elif args[0] in ("-r", "--reindex"):
            count = rag_engine.build_index()
            print(f"✓ Re-indexed {count} marketplace documents successfully.")
            return
        else:
            query_text = " ".join(args)

        print("=" * 60)
        print("⚡ ServeLocal RAG Query")
        print("=" * 60)
        print(f"Query: {query_text}\n")
        res = rag_engine.query(query_text)
        print(f"Answer ({res['provider']}):\n{res['answer']}\n")
        print("Sources retrieved:")
        for s in res.get("sources", []):
            print(f"  • {s['title']} [Score: {s['score']}]")
        if res.get("actions"):
            print("\nRecommended Next Steps:")
            for a in res["actions"]:
                print(f"  👉 {a['label']} -> {a['url']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
