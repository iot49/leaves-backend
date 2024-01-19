import machine   # type: ignore

RESET_CAUSE = {
    machine.PWRON_RESET: 'power-on',
    machine.HARD_RESET: 'hard reset',
    machine.WDT_RESET: 'watchdog timer',
    machine.DEEPSLEEP_RESET: 'deepsleep reset',
    machine.SOFT_RESET: 'soft reset'
}

print("reset-cause:", RESET_CAUSE.get(machine.reset_cause(), machine.reset_cause()))

print("soft reset - exiting to REPL")

if False:
    if machine.reset_cause == machine.SOFT_RESET:
        print("soft reset - exiting to REPL")
    else:    
        import asyncio
        from app import main
        print("starting from frozen main.py")
        asyncio.run(main())
        asyncio.new_event_loop()
        print("exiting to REPL")
