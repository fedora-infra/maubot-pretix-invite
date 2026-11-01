FROM dock.mau.dev/maubot/maubot
RUN pip install --upgrade pip --break-system-packages
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt --break-system-packages
