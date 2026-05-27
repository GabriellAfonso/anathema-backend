from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.


def websocket_test_view(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Teste WebSocket</title>
    </head>
    <body>
        <h1>Teste WebSocket</h1>
        <button onclick="sendMessage()">Enviar mensagem</button>

        <script>
            const socket = new WebSocket("ws://localhost:8000/ws/game/");

            socket.onopen = () => {
                console.log("Conectado ao WebSocket");
            };

            socket.onmessage = (event) => {
                console.log("Mensagem recebida:", event.data);
            };

            socket.onclose = () => {
                console.log("WebSocket fechado");
            };

            function sendMessage() {
                socket.send("Olá do navegador!");
            }
        </script>
    </body>
    </html>
    """
    return HttpResponse(html)
