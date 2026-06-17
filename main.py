import asyncio
import sys
from heavenly_capital.core.kernel import Kernel

async def main() -> None:
    async with Kernel() as kernel:
        await kernel.run(debug_mode=True)


if __name__ == "__main__":
    asyncio.run(main())


# checks = build_readiness_checks(db_connector=None, ibkr_gateway=None, eodhd_client=None)
