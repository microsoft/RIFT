openssl req -x509 -newkey rsa:2048 -nodes -days 825 -keyout rift_key.pem -out rift_cert.pem -subj "/CN=rift-server"
