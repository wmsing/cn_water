[nix]
channel = "stable-24_05"

[nix.nixpkgs]
python311Packages = ["pip"]

[env]
PYTHONUNBUFFERED = "1"

[[ports]]
localPort = 5000
externalPort = 80

[unitTest]
language = "python311"

[packager]
language = "python311"
ignoredPaths = ["node_modules"]
ignoredPackages = ["twitter", "facebook"]

[gitHubImport]
requiredFiles = ["replit.nix", "pyproject.toml", "poetry.lock", ".replit"]

[start]
initCmds = ["echo 'Starting...'"]

[sessions]
main = "python app_minimal.py"
