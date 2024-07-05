FROM dock.mau.dev/maubot/maubot
WORKDIR /maubot-events
RUN pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt