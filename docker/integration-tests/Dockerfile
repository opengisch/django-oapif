FROM opengisch/qgis:latest
COPY requirements.txt .
RUN apt update && apt install -y python3-pip
RUN pip3 install -r requirements.txt
# CMD ["python3", "-m", "pytest", "test_auth_from_qgis.py"]
WORKDIR /integration-tests
CMD ["xvfb-run", "python3", "-m", "unittest", "discover"]
