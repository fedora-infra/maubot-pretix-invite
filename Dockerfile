FROM dock.mau.dev/maubot/maubot
RUN pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt