import asyncio, sys
sys.path.insert(0, '/opt/whalex')

async def test():
    from radars.futures.engine import Signal
    from radars.futures.position_manager import open_from_signal, ACTIVE

    sig = Signal(
        symbol="ICPUSDT", direction="LONG", grade="A",
        score=7.5, confidence=90, entry=2.70, sl=2.6485,
        tp1=2.7687, tp2=2.8203, tp3=2.8890, leverage=6,
        strategies="Positive Delta\nFVG Bullish",
        radar_type="futures", tier="S",
    )
    print("🧪 Grade A...")
    pos = await open_from_signal(sig)
    print(f"✅ فُتحت: {pos.symbol} {pos.leverage}x" if pos else "❌ لم تُفتح")

    print("\n🧪 Grade C (يجب ترفض)...")
    sig_c = Signal(symbol="TESTUSDT", direction="LONG", grade="C",
        score=4.0, confidence=60, entry=1.0, sl=0.98,
        tp1=1.02, tp2=1.04, tp3=1.06, leverage=2,
        strategies="RSI", radar_type="futures", tier="B")
    pos_c = await open_from_signal(sig_c)
    print("✅ رُفضت بنجاح" if pos_c is None else "❌ فُتحت خطأ")

    print(f"\n═══ مفتوحة: {len(ACTIVE)} ═══")
    for pid, p in ACTIVE.items():
        print(f"  {p.symbol} {p.direction} Grade {p.grade}")

asyncio.run(test())
