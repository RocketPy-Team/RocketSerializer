import logging
import os

# Configure the logging settings
logging.basicConfig(
    filename="script.log",  # Specify the log file name
    level=logging.INFO,  # Set the logging level to INFO (you can adjust this as needed)
    format="%(asctime)s - %(levelname)s - %(message)s",  # Define log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define date and time format
)


def destroy_the_bank(file):
    """
    Run the 'ork2json' command on the given file.

    Args:
        file (str): The path to the .ork file.
    """
    cli = "ork2json"
    output = file[:-4]  # Remove '.ork' extension
    verbose = True

    command = f"{cli} --filepath {file} --output {output} --verbose {verbose}"
    logging.info(f"Executing command: {command}")

    try:
        import subprocess

        subprocess.run(command, shell=True, check=True)
        logging.info(f"Execution successful for file: {file}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error in file: {file}")
        logging.error(str(e))
        raise


if __name__ == "__main__":
    folder = "examples/databank"

    ork_files = [
        folder + "/" + name + "/rocket.ork"
        for name in os.listdir(folder)
        if name.startswith("Team")
    ]

    for file in ork_files:
        try:
            destroy_the_bank(file)
        except Exception as e:
            # Log any unexpected exceptions
            logging.exception(f"An unexpected error occurred in file: {file}")
