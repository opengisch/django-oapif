FROM opengisch/qgis:latest
COPY requirements.txt .
RUN apt update && apt install -y python3-pip
RUN pip3 install -r requirements.txt
WORKDIR /integration-tests