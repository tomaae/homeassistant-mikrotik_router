import configparser


def main():
    parser = configparser.ConfigParser()
    parser.read("Pipfile")

    packages = "packages"
    with open("requirements.txt", "w") as f:
        for key in parser[packages]:
            value = parser[packages][key]
            f.write(key + value.replace('"', "") + "\n")

    devpackages = "dev-packages"
    with open("requirements_tests.txt", "w") as f:
        for key in parser[devpackages]:
            value = parser[devpackages][key]
            f.write(key + value.replace('"', "") + "\n")


if __name__ == "__main__":
    main()
