from setuptools import find_packages, setup


setup(
    name="ai-accounting-copilot",
    version="0.1.0",
    description="AI Pre-Accounting Copilot scaffold",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Pillow>=10.0.0",
        "pytesseract>=0.3.10",
        "openai>=1.40.0",
        "fastapi>=0.115.0",
        "uvicorn>=0.30.0",
        "python-dotenv>=1.0.1",
    ],
)
