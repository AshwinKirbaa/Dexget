import PyInstaller.__main__
import importlib.util

def build():
    # Basic PyInstaller arguments
    args = [
        'launcher.py',            # The main script
        '--name=JarvisAgent',     # Name of the executable
        '--onefile',              # Create a single executable
        
        '--hidden-import=jarvis',
        '--hidden-import=jarvis_integration',
        '--hidden-import=jarvis.model_runtime',
        '--hidden-import=main',
        '--exclude-module=PySide6',
        '--windowed',              # Copilot key launch must not open a console
        '--clean'                 # Clean PyInstaller cache
    ]

    # ARM64 intentionally omits unavailable voice packages. Collect optional
    # packages only when they are actually installed in the build interpreter.
    for package in ('vosk', 'chromadb', 'sentence_transformers', 'faster_whisper', 'winrt'):
        if importlib.util.find_spec(package) is not None:
            args.append(f'--collect-all={package}')

    print(f"Running PyInstaller with args: {args}")
    PyInstaller.__main__.run(args)
    print("Build complete! Check the 'dist' directory for JarvisAgent.exe.")

if __name__ == '__main__':
    build()
