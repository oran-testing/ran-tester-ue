import json
import socket
import subprocess


def start_subprocess(command):
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True)
    return process


def kill_subprocess(process):
    process.terminate()  # Graceful termination
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()  # Forceful termination
    process.communicate()


def bytes_to_binary(byte_obj):
    """Convert a bytes object to a binary string."""
    return "".join(f"{byte:08b}" for byte in byte_obj)


def binary_to_bytes(binary_str):
    """Convert a binary string to a bytes object."""
    return int(binary_str, 2).to_bytes((len(binary_str) + 7) // 8, byteorder="big")


def extract_bits(byte_obj, start_bit, end_bit):
    """Extract bits from start_bit to end_bit from a bytes object."""
    binary_str = bytes_to_binary(byte_obj)
    extracted_bits = binary_str[start_bit:end_bit]
    extracted_bytes = binary_to_bytes(extracted_bits)

    return extracted_bits, extracted_bytes


def shift_bits_left(binary_str, shift_amount):
    """Shift the binary string left by the specified amount of bits."""
    shifted_binary_str = binary_str[shift_amount:]
    shifted_binary_str = shifted_binary_str.ljust(len(binary_str), "0")
    return shifted_binary_str


def shift_bytes_left(byte_obj, shift_amount):
    """Shift bytes left by the specified number of bits."""
    binary_str = bytes_to_binary(byte_obj)

    shifted_binary_str = shift_bits_left(binary_str, shift_amount)

    shifted_bytes = binary_to_bytes(shifted_binary_str)

    return shifted_bytes

def send_command(ip, port, cmd_json):
    try:
        cmd_string = json.dumps(cmd_json)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            print(type(ip), type(port), type(cmd_string))
            sock.connect((ip, port))
            sock.sendall(cmd_string.encode('utf-8'))
            print("SENDING:", cmd_string)
            
            # Move recv inside the with block to keep socket open
            response = sock.recv(1024).decode('utf-8').strip()
            if json.loads(response)["result"] == "Success":
                print("RECEIVED: Success")
                return 0
            else:
                print("RECEIVED: Failure")
                raise ValueError("Received Failure from gNB controller")

    except Exception as e:
        print(f"(send_command) An error occurred: {e}")
