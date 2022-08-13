import  cups

conn = cups.Connection()
print(conn)
printers = conn.getPrinters()
print(printers)
default_printer = list(printers.keys())[0]
print(default_printer)
cups.setUser('kidier')
#conn.printFile(default_printer, self.image_reader.output_image_path, "boothy", {'fit-to-page': 'True'})