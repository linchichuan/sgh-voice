import ApplicationServices

def check_accessibility(prompt=True):
    if prompt:
        options = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
        return ApplicationServices.AXIsProcessTrustedWithOptions(options)
    else:
        return ApplicationServices.AXIsProcessTrusted()

print(check_accessibility())
