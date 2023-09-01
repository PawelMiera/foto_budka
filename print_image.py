import cups
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fotobudka',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f', '--filename', help='Print filename', default='', type=str)
    args = parser.parse_args()

    conn = cups.Connection()
    printers = conn.getPrinters()
    default_printer = list(printers.keys())[0]
    print("Found printer: ", default_printer)
    conn.printFile(default_printer, args.filename, "boothy", {'fit-to-page': 'True'})
    print("Print job successfully created: ", args.filename)
