import reportlab.pdfbase as rb
print("Attributes in reportlab.pdfbase:")
for attr in dir(rb):
    if not attr.startswith('_'):
        print(f"  {attr}")

# Try to find the registerFont function
if hasattr(rb, 'registerFont'):
    print("Found registerFont in reportlab.pdfbase")
else:
    print("registerFont not found in reportlab.pdfbase")
    # Check submodules
    import reportlab.pdfbase.ttfonts as tt
    print("Attributes in reportlab.pdfbase.ttfonts:")
    for attr in dir(tt):
        if not attr.startswith('_'):
            print(f"  {attr}")