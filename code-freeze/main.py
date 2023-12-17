# default: 
#       start the app

# development mode: 
#       create a custom /main.py that 
#       will be executed instead of starting the app

try:

    print("NOTE: try starting app from /main.py")
    open("/main.py")      # OSError if file does not exist
    __import__("main")    # import /main.py

except Exception:

    print("NOTE: failed loading /main.py ... normal app start from frozen main.py")

    import asyncio
    from app import main

    asyncio.run(main())
    asyncio.new_event_loop()

    print("FATAL: frozen main.py returned (wdt?)")
