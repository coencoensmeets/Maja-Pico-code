import network

def scan_networks():
    # Initialize the Wi-Fi interface in station mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Scan for available networks
    networks = wlan.scan()
    
    # Print the results
    print("Available networks:")
    for net in networks:
        ssid = net[0].decode('utf-8')
        bssid = ':'.join('%02x' % b for b in net[1])
        channel = net[2]
        RSSI = net[3]
        authmode = net[4]
        hidden = net[5]
        
        print(f"SSID: {ssid}, BSSID: {bssid}, Channel: {channel}, RSSI: {RSSI}, Authmode: {authmode}, Hidden: {hidden}")

if __name__ == "__main__":
    scan_networks()