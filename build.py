import PyInstaller.__main__

def build():
    # Basic PyInstaller arguments
    args = [
        'launcher.py',            # The main script
        '--name=JarvisAgent',     # Name of the executable
        '--onefile',              # Create a single executable
        
        # We need to collect some tricky packages
        # Uncomment these if you encounter missing module errors when running the exe:
        '--collect-all=vosk',
        '--collect-all=chromadb',
        '--collect-all=sentence_transformers',
        '--collect-all=faster_whisper',
        
        '--hidden-import=jarvis',
        '--hidden-import=jarvis_integration',
        '--hidden-import=legacy_jarvis',
        '--hidden-import=main',
        '--exclude-module=PySide6',
        '--clean'                 # Clean PyInstaller cache
    ]

    print(f"Running PyInstaller with args: {args}")
    PyInstaller.__main__.run(args)
    print("Build complete! Check the 'dist' directory for JarvisAgent.exe.")

if __name__ == '__main__':
    build()
