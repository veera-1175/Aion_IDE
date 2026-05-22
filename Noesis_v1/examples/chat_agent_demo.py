"""Interactive persistent agent demo — terminal chat with Noesis memory."""

from __future__ import annotations

from noesis.agents.persistent_agent import PersistentAgent


def main():
    print("=" * 60)
    print("  Noesis Persistent Agent")
    print("  Type 'quit' to exit | 'stats' | 'share <url>'")
    print("=" * 60)

    agent = PersistentAgent(agent_id="demo-agent", db_path="data/chat_agent.db")

    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user:
            continue
        if user.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break
        if user.lower() == "stats":
            print(agent.summary())
            continue
        if user.lower().startswith("share "):
            url = user.split(maxsplit=1)[1]
            print(agent.share_with_agent(url))
            continue
        if user.lower().startswith("learn "):
            fact = user.split(maxsplit=1)[1]
            print(agent.teach(fact))
            continue

        result = agent.chat(user)
        print(f"\n[Memory] Recalled {result['recalled_count']} contexts")
        print(result["memory_context"])
        print(f"\n[LLM Prompt Preview]\n{result['suggested_system_prompt'][:400]}...")


if __name__ == "__main__":
    main()
