# test_connection.py
import socket
from threading import Thread
import time

def create_test_server(port=6000):
    """创建一个简单的TCP测试服务器"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen()
        print(f"测试服务器在端口 {port} 上监听...")
        
        while True:
            conn, addr = s.accept()
            print(f"接收到来自 {addr} 的连接")
            conn.sendall(b"TEST_SERVER_RESPONSE_OK\n")
            conn.close()

# 在后台启动测试服务器
test_thread = Thread(target=create_test_server, daemon=True)
test_thread.start()

# 保持主线程运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("测试服务器关闭")