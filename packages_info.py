# package_info.py — Helper functions to access business data

from packages import DESTINATIONS, SERVICES, POLICIES, CONTACT

def get_destination_info(destination_name: str) -> dict:
    """Get detailed info about a destination"""
    dest = destination_name.lower().strip()
    
    for key, data in DESTINATIONS.items():
        if key in dest or dest in key:
            return data
    
    return None

def get_service_info(service_type: str) -> dict:
    """Get detailed info about a service"""
    service = service_type.lower().strip()
    
    for key, data in SERVICES.items():
        if key in service or service in key:
            return data
    
    return None

def get_all_packages_summary() -> str:
    """Return a formatted list of all packages"""
    summary = "📍 AVAILABLE DESTINATIONS & PACKAGES:\n\n"
    
    for destination, data in DESTINATIONS.items():
        summary += f"🏖️ {data['country'].upper()}\n"
        for pkg in data['packages']:
            summary += f"  • {pkg['name']}: {pkg['nights']} nights, ₹{pkg['price_per_person']:,}/person\n"
        summary += "\n"
    
    return summary

def get_all_services_summary() -> str:
    """Return a formatted list of all services"""
    summary = "✨ ADD-ON SERVICES:\n\n"
    
    for key, service in SERVICES.items():
        summary += f"{service.get('icon', '•')} {service['name']}\n"
    
    return summary

def format_destination_details(destination_name: str) -> str:
    """Format destination info for the AI to present to user"""
    dest_info = get_destination_info(destination_name)
    
    if not dest_info:
        return None
    
    output = f"📍 {dest_info['country'].upper()}\n\n"
    
    for pkg in dest_info['packages']:
        output += f"🏨 {pkg['name']}\n"
        output += f"   Duration: {pkg['nights']} nights\n"
        output += f"   Price: ₹{pkg['price_per_person']:,} per person\n"
        output += f"   Best for: {pkg.get('best_for', 'All travelers')}\n"
        output += f"   Highlights:\n"
        
        for highlight in pkg['highlights']:
            output += f"   • {highlight}\n"
        
        output += "\n"
    
    return output

def format_service_details(service_name: str) -> str:
    """Format service info for the AI to present"""
    service = get_service_info(service_name)
    
    if not service:
        return None
    
    output = f"{service.get('icon', '')} {service['name']}\n\n"
    
    if 'options' in service:
        for option in service['options']:
            if isinstance(option, dict):
                for key, value in option.items():
                    output += f"  {key.replace('_', ' ').title()}: {value}\n"
            output += "\n"
    
    return output

def get_price_for_service(service_name: str, variant: str = None) -> int:
    """Get price for a specific service"""
    service = get_service_info(service_name)
    
    if not service:
        return None
    
    # Direct price
    if 'price' in service:
        return service['price']
    
    # Search in options
    if 'options' in service:
        for option in service['options']:
            if isinstance(option, dict):
                # Check for direct match on name/type
                if 'name' in option and variant and variant.lower() in option['name'].lower():
                    return option.get('price', option.get('price_per_night', option.get('price_per_day')))
                if 'type' in option and variant and variant.lower() in option['type'].lower():
                    return option.get('price', option.get('price_per_night', option.get('price_per_day')))
    
    return None

# Example usage for the system prompt:
if __name__ == "__main__":
    print(get_all_packages_summary())
    print("\n" + "="*50 + "\n")
    print(get_all_services_summary())
    print("\n" + "="*50 + "\n")
    print(format_destination_details("bali"))
