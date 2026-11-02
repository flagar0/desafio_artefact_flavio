"""Terminal chat with the agent (for quick tests / recording example conversations).

Usage: python -m app.cli --customer 1 [--fresh]
"""
import argparse

from app import repository as repo
from app.agent.agent import AgentRuntime, handle_customer_message
from app.storage import chat_store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", type=int, default=1)
    ap.add_argument("--fresh", action="store_true", help="clear the stored conversation first")
    args = ap.parse_args()

    customer = repo.get_customer(args.customer)
    if args.fresh:
        chat_store.reset_conversation(args.customer)
    print(f"Chatting as {customer['name']} (id {args.customer}). Ctrl+C to exit.\n")
    runtime = AgentRuntime()
    try:
        while True:
            text = input("Cliente> ").strip()
            if not text:
                continue
            reply = handle_customer_message(runtime, args.customer, text)
            if reply is None:
                print("[agente em silêncio: conversa com a equipe]\n")
                continue
            print(f"\nLéo> {reply.text}\n   (tools: {reply.tools_used or '-'})\n")
            if reply.handoff:
                print("   🔴 HANDOFF solicitado ao lojista\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        runtime.close()


if __name__ == "__main__":
    main()

