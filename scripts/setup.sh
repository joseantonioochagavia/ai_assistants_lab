#!/usr/bin/env bash

#!/usr/bin/env bash

set -e

PYTHON_VERSION="3.10.13"
ENV_NAME="ai-assistants"

echo ">>> Checking pyenv installation..."
if ! command -v pyenv >/dev/null 2>&1; then
  echo "Error: pyenv is not installed or not available in PATH."
  exit 1
fi

echo ">>> Installing Python ${PYTHON_VERSION} if needed..."
pyenv install -s "${PYTHON_VERSION}"

echo ">>> Creating virtual environment '${ENV_NAME}' if needed..."
if ! pyenv versions --bare | grep -qx "${ENV_NAME}"; then
  pyenv virtualenv "${PYTHON_VERSION}" "${ENV_NAME}"
else
  echo "Virtual environment '${ENV_NAME}' already exists."
fi

echo ">>> Setting local pyenv environment to '${ENV_NAME}'..."
pyenv local "${ENV_NAME}"

echo ">>> Upgrading pip..."
python -m pip install --upgrade pip

echo ">>> Installing project requirements..."
python -m pip install -r requirements.txt

echo ">>> Setup complete."
echo "Local environment set to: ${ENV_NAME}"
echo "You can confirm with: pyenv version"