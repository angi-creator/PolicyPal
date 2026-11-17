# PolicyPal

PolicyPal is a Streamlit app that pulls Texas filed bills, ranks them by policy priorities, and highlights the most relevant legislation for labor, infrastructure, workforce, affordability, and accountability issues.

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

## Deploy to Streamlit Cloud

1. Push this repo to GitHub.
2. Sign in to Streamlit Cloud.
3. Select "New app".
4. Choose this repository.
5. Set the app file to `app.py`.
6. Deploy.

The app will run with the dependencies from `requirements.txt`.

## Notes

- The app fetches the live Texas Legislature report pages.
- It depends on outbound internet access from the deployment environment.
- If you want to change your policy ranking logic, update the keyword maps in `app.py`.
