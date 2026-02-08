import gradium
import inspect

print("Inspecting STTSetup...")
try:
    # It might be exposed as gradium.STTSetup or gradium.speech.STTSetup
    if hasattr(gradium, "STTSetup"):
        cls = gradium.STTSetup
    elif hasattr(gradium, "speech") and hasattr(gradium.speech, "STTSetup"):
        cls = gradium.speech.STTSetup
    else:
        # Try to find it in client module if that's where it was used in docs
        # The docs said setup: 'speech.STTSetup'
        # Let's look at gradium.client imports or just dir(gradium)
        print("Could not find STTSetup directly. listing gradium contents:")
        print(dir(gradium))
        cls = None

    if cls:
        print(inspect.getdoc(cls))
        print(inspect.signature(cls))
        # Also print attributes if it's a dataclass or pydantic model
        if hasattr(cls, "__annotations__"):
            print("Annotations:", cls.__annotations__)

except Exception as e:
    print(f"Error: {e}")
