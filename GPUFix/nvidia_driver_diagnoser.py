import subprocess
import sys

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"Command not found: {command.split()[0]}")
        return None

def diagnose_nvidia_driver():
    print("--- NVIDIA Driver Diagnoser ---")
    print("This script will help diagnose common issues related to NVIDIA drivers.")
    print("It cannot fix issues directly but will provide guidance.")
    print("-" * 30)

    print("\n1. Checking for NVIDIA kernel module...")
    nvidia_module_status = run_command("lsmod | grep nvidia")
    if nvidia_module_status:
        print("   NVIDIA kernel module appears to be loaded.")
        print(f"   Output: {nvidia_module_status.splitlines()[0]}")
    else:
        print("   NVIDIA kernel module does NOT appear to be loaded.")
        print("   This is a common reason for 'NVML Error: Driver Not Loaded'.")
        print("\n   Suggested actions:")
        print("   - Try to load the module manually: sudo modprobe nvidia")
        print("   - Reinstall your NVIDIA drivers. Visit NVIDIA's website or your distribution's documentation for instructions.")
        print("   - Ensure Secure Boot is disabled in your BIOS/UEFI if you are using unsigned drivers.")

    print("\n2. Checking NVIDIA driver version (if nvidia-smi is available)...")
    nvidia_smi_output = run_command("nvidia-smi")
    if nvidia_smi_output:
        print("   nvidia-smi command found. Driver information:")
        print(nvidia_smi_output)
    else:
        print("   nvidia-smi command not found or failed to execute.")
        print("   This usually means NVIDIA drivers are not installed or not configured correctly.")
        print("\n   Suggested actions:")
        print("   - Install NVIDIA drivers for your GPU and operating system.")
        print("   - Ensure NVIDIA binaries are in your system's PATH.")

    print("\n3. Checking system logs for NVIDIA-related errors...")
    dmesg_output = run_command("dmesg | grep -i nvidia")
    if dmesg_output:
        print("   Recent kernel messages related to NVIDIA:")
        print(dmesg_output)
    else:
        print("   No recent kernel messages related to NVIDIA found in dmesg.")

    print("\n--- Diagnosis Complete ---")
    print("Please review the output above and follow the suggested actions.")
    print("If the issue persists, consider seeking help from your Linux distribution's community or NVIDIA support.")

if __name__ == "__main__":
    diagnose_nvidia_driver()
