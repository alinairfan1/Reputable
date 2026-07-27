# Contributing to Reputable

First off, thank you for considering contributing to Reputable! It's people like you that make Reputable such a great tool for the GitHub community.

## Where do I go from here?

If you've noticed a bug or have a feature request, make sure to check our [Issues](https://github.com/alinairfan1/Reputable/issues) first to see if someone else has already created a ticket. If not, go ahead and [make one](https://github.com/alinairfan1/Reputable/issues/new/choose)!

## Running the ML Pipeline Locally

If you want to train the model yourself or improve the dataset:

1. Clone the repository
2. Install the backend dev requirements: `pip install -r backend/requirements-dev.txt`
3. Generate a new dataset: `python scripts/ml/collect_data.py` (requires `GITHUB_TOKEN` in `backend/.env`)
4. Label the dataset: `python scripts/ml/auto_labeler.py`
5. Train the Random Forest: `python scripts/ml/train_model.py`
6. Move the resulting `.pkl` file into `backend/github_quality_rf_model.pkl`.

## Running the App Locally

To run the full stack:
- Backend: `uvicorn main:app --reload --app-dir backend`
- Frontend: `cd frontend && npm install && npm run dev`

Or just use Docker:
`docker compose up --build`

## Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Ensure the test suite passes (`pytest tests/`).
4. Make sure your code lints.
5. Issue that pull request!
