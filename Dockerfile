FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive 

# update and install required packages
RUN apt-get update && apt-get install -y \
    wget gnupg apt-transport-https fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 libcups2 \
    libcurl4 libdbus-1-3 libdrm2 libexpat1 libgbm1 libglib2.0-0 libgtk-3-0 \
    libnspr4 libnss3 libpango-1.0-0 libvulkan1 libx11-6 libxcb1 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 \
    libxrandr2 xdg-utils tmux vim make curl && \
    rm -rf /var/lib/apt/lists/*

# install google chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm ./google-chrome-stable_current_amd64.deb

# add a non-root user
RUN useradd -m -s /bin/bash agent
USER agent
WORKDIR /home/agent

ENV PATH="/home/agent/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# copy over the makefile and project spec
# the license and readme are needed for to make install via the pyproject.toml
COPY --chown=agent:agent pyproject.toml .
COPY --chown=agent:agent README.md .
COPY --chown=agent:agent LICENSE .
RUN mkdir echos_lab

# Install just the project dependencies
# This wont install echos_lab yet since the source code hasn't been copied over
RUN pip install .

# Then copy over the source code and install echos
# This also uninstalls uvloop
COPY --chown=agent:agent Makefile .
COPY --chown=agent:agent ./echos_lab ./echos_lab
COPY --chown=agent:agent ./start.sh ./start.sh

RUN make install

# start the main script
CMD ["sh", "start.sh"]
