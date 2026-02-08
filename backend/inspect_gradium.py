import gradium
import inspect

print("Inspecting GradiumClient.stt_stream...")
try:
    print(inspect.getdoc(gradium.client.GradiumClient.stt_stream))
    print(inspect.signature(gradium.client.GradiumClient.stt_stream))
except Exception as e:
    print(f"Error: {e}")

print("\nInspecting GradiumClient.stt...")
try:
    print(inspect.getdoc(gradium.client.GradiumClient.stt))
except Exception as e:
    print(f"Error: {e}")
