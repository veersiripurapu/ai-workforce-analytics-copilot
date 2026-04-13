# AI Workforce Analytics Copilot

An AI-powered analytics assistant that helps operations leaders answer questions like:

- Which region has the lowest volume?
- Why is performance dropping?
- What risks are emerging?
- What will happen next week?

---

## Features

- Natural language Q&A  
- Executive summary  
- Root cause analysis  
- Trend & risk detection  
- Forecasting & early warning  
- Scenario simulation  

---

## Tech Stack

- Python  
- Streamlit  
- Pandas  
- OpenAI  

---

## Data Sources

- Payroll data (Excel)  
- Volume data (CSV)  

---

## ▶️ How to Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 🌐 Live Application

👉 [Launch Streamlit App](https://ai-workforce-analytics-copilot-5uhzuzomv2veycekeqz32h.streamlit.app/)

---

## 📊 Power BI Dashboard

This project also includes a Power BI dashboard used for workforce analytics and KPI visualization.

- 📂 **PBIX File**: [Download Dashboard](https://drive.google.com/file/d/1-OyGObenDuhfDGI_THRKelUzcJsMzhGp/view?usp=drive_link)  
- 📸 **Screenshots**: [View Screenshots](https://drive.google.com/drive/folders/1bvh9BTCtPEY1ktzUTPT23NWjnDQe16Oy?usp=drive_link)

This dashboard represents the foundational analytics layer, which is enhanced with AI-driven insights through the Streamlit application.

---

## 🏗️ Architecture

- **Source Control**: GitHub  
- **Hosting**: Streamlit Cloud  
- **AI Layer**: OpenAI API (secured via environment variables / secrets)  

Data flows from structured files → processed in Python → enhanced with AI → visualized via Streamlit UI.

---

## 🔒 Security Note

API keys and sensitive credentials are not stored in the repository.  
They are securely managed using environment variables / Streamlit secrets.

---
