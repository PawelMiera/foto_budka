import  cups

conn = cups.Connection()
print(conn)
printers = conn.getPrinters()
print(printers)
default_printer = list(printers.keys())[0]
print(default_printer)
cups.setUser('kidier')
conn.printFile(default_printer, "saved_images/45/razem.png", "boothy", {'fit-to-page': 'True', 'media': "FotobudkaA6"})