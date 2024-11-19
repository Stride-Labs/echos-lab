FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app/tee-bot:$PYTHONPATH

# update and install required packages
RUN apt-get update && apt-get install -y \
    wget gnupg apt-transport-https fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 libcups2 \
    libcurl4 libdbus-1-3 libdrm2 libexpat1 libgbm1 libglib2.0-0 libgtk-3-0 \
    libnspr4 libnss3 libpango-1.0-0 libvulkan1 libx11-6 libxcb1 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 \
    libxrandr2 xdg-utils tmux vim && \
    rm -rf /var/lib/apt/lists/*

# install google chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm ./google-chrome-stable_current_amd64.deb

# copy the local folder to /app/tee-bot in the container
COPY ./requirements.txt /app/tee-bot/echos_lab/requirements.txt

RUN pip install -r /app/tee-bot/echos_lab/requirements.txt

# uninstall uvloop without breaking system packages
RUN pip uninstall -y uvloop

COPY ./ /app/tee-bot/echos_lab/

# remove .env
RUN rm /app/tee-bot/echos_lab/.env

# set the working directory
WORKDIR /app/tee-bot/echos_lab

# start the main script
CMD ["sh", "/app/tee-bot/echos_lab/init_bot.sh"]

