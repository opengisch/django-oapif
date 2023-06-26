FROM qgis/qgis:latest
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD ["pytest", "test_auth_from_qgis.py"]
