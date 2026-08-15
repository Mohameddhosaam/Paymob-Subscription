from paymob_client import PaymobClient, PaymobError

AMOUNT_CENTS = 10000  # 100.00 EGP


def main():
    client = PaymobClient()

    print("1) Creating subscription plan...")
    plan = client.create_subscription_plan(
        name="Monthly Pro Plan",
        amount_cents=AMOUNT_CENTS,
        frequency_days=30,
    )
    plan_id = plan["id"]
    print(f"   -> plan_id: {plan_id}")

    print("\n2) Creating subscription (needs a real card + 3DS entry)...")
    print("   Open this URL in a browser and complete checkout with a test card:")
    print(f"   http://localhost:5000/subscribe/{plan_id}/{AMOUNT_CENTS}")
    input("   Press Enter here once checkout is complete...")

    print("\n   Looking up the subscription by plan_id...")
    subs = client.find_subscriptions_by_plan(plan_id)
    results = subs.get("results", [])
    if not results:
        raise RuntimeError(
            f"No subscription found for plan_id={plan_id}. Checkout may not have "
            "completed successfully — check app.py's terminal for webhook logs, "
            "and check the Paymob dashboard's Transactions page for this plan."
        )
    subscription_id = results[0]["id"]
    print(f"   -> subscription_id: {subscription_id}")

    print("\n3) Adding a secondary card (needs a SECOND real card + 3DS entry)...")
    print("   Open this URL in a browser and complete checkout with a DIFFERENT test card:")
    print(f"   http://localhost:5000/subscribe/add-card/{subscription_id}/{AMOUNT_CENTS}")
    input("   Press Enter here once checkout is complete...")

    print("\n   Listing subscription cards...")
    cards = client.list_subscription_cards(subscription_id)
    print(f"   -> cards: {cards}")
    secondary = next((c for c in cards if not c.get("is_primary")), None)
    if not secondary:
        raise RuntimeError(
            "No secondary (non-primary) card found on the subscription. "
            "Check that the second checkout used a different card and completed successfully."
        )
    secondary_card_id = secondary["id"]
    print(f"   -> secondary card id: {secondary_card_id}")

    print("\n4) Changing primary card to the secondary one...")
    try:
        changed = client.change_primary_card(subscription_id, secondary_card_id)
        print("   -> result:", changed)
    except PaymobError as e:
        print(f"   -> FAILED: {e}")

    print("\n5) Suspending the subscription...")
    try:
        suspended = client.suspend_subscription(subscription_id)
        print("   -> result:", suspended)
    except PaymobError as e:
        print(f"   -> FAILED: {e}")

    print("\nDone. Current state:")
    print(client.get_subscription(subscription_id))


if __name__ == "__main__":
    main()