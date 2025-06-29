import subprocess
import sys

def run_command(command, check=True, shell=True, capture_output=True, text=True):
    try:
        print(f"Executing: {command}")
        result = subprocess.run(command, shell=shell, capture_output=capture_output, text=text, check=check)
        if result.stdout:
            print("Stdout:")
            print(result.stdout.strip())
        if result.stderr:
            print("Stderr:")
            print(result.stderr.strip())
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Return Code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Command not found: {command.split()[0]}")
        return False

def install_nvidia_drivers():
    print("--- NVIDIA Driver Installation Script (Manjaro) ---")
    print("This script attempts to install recommended NVIDIA drivers using mhwd.")
    print("\nWARNING: This script will make system-level changes and requires sudo privileges.")
    print("         Ensure you have backed up important data before proceeding.")
    print("-----------------------------------------------------")

    if not run_command("which mhwd", check=False):
        print("Error: mhwd (Manjaro Hardware Detection) not found.")
        print("This script is designed for Manjaro Linux. Please ensure mhwd is installed.")
        sys.exit(1)

    print("\n1. Listing available NVIDIA drivers...")
    if not run_command("mhwd -l | grep -i nvidia", check=False):
        print("No NVIDIA drivers found by mhwd. This might indicate a problem with your mhwd configuration or repositories.")
        print("Please ensure your system is up-to-date and repositories are correctly configured.")
        sys.exit(1)

    print("\n2. Attempting to resolve potential conflicts by removing nvidia-dkms...")
    print("You may be prompted for your sudo password.")
    run_command("sudo pacman -Rdd --noconfirm nvidia-dkms", check=False)

    print("\n3. Attempting to auto-install recommended non-free NVIDIA drivers...")
    # Use -a pci nonfree 0300 for auto-installing recommended non-free drivers for VGA compatible controller
    if run_command("sudo mhwd -a pci nonfree 0300", check=False):
        print("\nNVIDIA driver installation initiated successfully (or no changes were needed).")
        print("It is highly recommended to **REBOOT YOUR SYSTEM** now for the changes to take effect.")
        print("After rebooting, you can run 'nvidia-smi' in your terminal to verify the installation.")
    else:
        print("\nNVIDIA driver installation failed or encountered an issue.")
        print("Please review the error messages above. You may need to manually troubleshoot or install drivers.")
        print("Refer to Manjaro's official documentation or forums for further assistance.")

    print("\n--- Script Finished ---")

if __name__ == "__main__":
    install_nvidia_drivers()
