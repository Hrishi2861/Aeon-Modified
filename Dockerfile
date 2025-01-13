FROM 5hojib/aeon:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN uv pip install --break-system-packages --system --no-cache-dir -r requirements.txt

COPY . .
CMD ["bash", "start.sh"]
