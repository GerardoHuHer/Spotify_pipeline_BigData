FROM python

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN python run_pipeline.py

RUN python run_pipeline.py --layer ml

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py"]