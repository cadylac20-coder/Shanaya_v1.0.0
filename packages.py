# packages.py — MKOV Business Data

DESTINATIONS = {
    "bali": {
        "country": "Indonesia",
        "packages": [
            {
                "name": "Bali Romance",
                "nights": 7,
                "price_per_person": 62000,
                "currency": "INR",
                "highlights": [
                    "Private villa in Seminyak",
                    "Daily spa treatments",
                    "Cooking class + private chef dinner",
                    "Temple tours & rice paddy hikes"
                ],
                "best_for": "Couples, Honeymoon"
            },
            {
                "name": "Bali Adventure",
                "nights": 5,
                "price_per_person": 45000,
                "highlights": [
                    "Surfing lessons in Uluwatu",
                    "Mount Batur sunrise trek",
                    "White water rafting",
                    "Ubud cultural tour"
                ],
                "best_for": "Adventure seekers, Young couples"
            }
        ]
    },
    "goa": {
        "country": "India",
        "packages": [
            {
                "name": "Goa Beach Escape",
                "nights": 4,
                "price_per_person": 18000,
                "highlights": [
                    "4-star beachfront resort",
                    "Water sports package included",
                    "Backwater cruise",
                    "Night market tour"
                ],
                "best_for": "Families, Beach lovers"
            }
        ]
    },
    "kerala": {
        "country": "India",
        "packages": [
            {
                "name": "Kerala Backwaters Paradise",
                "nights": 5,
                "price_per_person": 35000,
                "highlights": [
                    "Houseboat cruise (3 nights)",
                    "Spice plantation tour",
                    "Ayurvedic spa treatments",
                    "Chinese fishing net demo"
                ],
                "best_for": "Couples, Relaxation seekers"
            }
        ]
    },
    "ladakh": {
        "country": "India",
        "packages": [
            {
                "name": "Ladakh Adventure Trek",
                "nights": 6,
                "price_per_person": 28000,
                "highlights": [
                    "High altitude trekking",
                    "Leh-Ladakh scenic drive",
                    "Pangong Lake visit",
                    "Buddhist monasteries"
                ],
                "best_for": "Adventure enthusiasts, Nature lovers"
            }
        ]
    },
    "thailand": {
        "country": "Thailand",
        "packages": [
            {
                "name": "Thailand Grand Tour",
                "nights": 9,
                "price_per_person": 55000,
                "highlights": [
                    "Bangkok city tour",
                    "Phuket beach resort",
                    "Phi Phi Islands cruise",
                    "Chiang Mai temple visit"
                ],
                "best_for": "First-time visitors, Culture + beach"
            }
        ]
    }
}

SERVICES = {
    "visa_assistance": {
        "name": "Visa Assistance",
        "icon": "🛂",
        "options": [
            {
                "type": "Tourist Visa",
                "price": 3000,
                "processing_days": "5-7",
                "includes": [
                    "Document verification",
                    "Embassy submission",
                    "Interview preparation"
                ]
            },
            {
                "type": "Business Visa",
                "price": 5000,
                "processing_days": "7-10",
                "includes": [
                    "Business letter verification",
                    "Corporate documents",
                    "Expedited processing"
                ]
            },
            {
                "type": "Multiple Entry Visa",
                "price": 8000,
                "processing_days": "10-14"
            }
        ]
    },
    "travel_insurance": {
        "name": "Travel Insurance",
        "icon": "🛡️",
        "options": [
            {
                "name": "Basic Coverage",
                "price": 2500,
                "covers": ["Medical emergencies", "Luggage loss", "Flight delays"]
            },
            {
                "name": "Premium Coverage",
                "price": 4500,
                "covers": ["Medical", "Luggage", "Trip cancellation", "Delays up to 12hrs"]
            },
            {
                "name": "Comprehensive Coverage",
                "price": 6500,
                "covers": ["All premium coverage", "Adventure sports", "Extreme weather", "Evacuation"]
            }
        ]
    },
    "airport_transfer": {
        "name": "Airport Transfer",
        "icon": "🚗",
        "options": [
            {"vehicle": "Sedan", "passengers": "1-3", "price": 1200},
            {"vehicle": "SUV", "passengers": "4-6", "price": 1800},
            {"vehicle": "Tempo", "passengers": "7+", "price": 2500}
        ]
    },
    "hotel_upgrade": {
        "name": "Hotel Upgrade",
        "icon": "🏨",
        "options": [
            {"from": "3-star", "to": "4-star", "price_per_night": 3000},
            {"from": "4-star", "to": "5-star", "price_per_night": 5000},
            {"from": "Any", "to": "Luxury resort", "price_per_night": 8000}
        ]
    },
    "meal_plan": {
        "name": "Meal Plan",
        "icon": "🍽️",
        "options": [
            {"type": "Breakfast only", "price_per_day": 1500},
            {"type": "Half board (Breakfast + Dinner)", "price_per_day": 2500},
            {"type": "Full board (B+L+D)", "price_per_day": 4000}
        ]
    },
    "travel_sim": {
        "name": "International SIM",
        "icon": "📱",
        "price": 800,
        "includes": "₹500 credit + local number",
        "data_plans": {
            "1GB": 150,
            "5GB": 500,
            "10GB": 800
        }
    },
    "forex_card": {
        "name": "Forex Card",
        "icon": "💱",
        "price": 500,
        "features": [
            "Zero markup on international transactions",
            "24/7 customer support",
            "Multi-currency loading",
            "ATM withdrawal enabled"
        ]
    },
    "activity_package": {
        "name": "Activity Package",
        "icon": "🎯",
        "options": [
            {
                "name": "Adventure Package",
                "price": 3500,
                "activities": ["Trekking", "Rafting", "Rock climbing"]
            },
            {
                "name": "Cultural Package",
                "price": 2500,
                "activities": ["Museum tours", "Heritage walks", "Local cooking"]
            },
            {
                "name": "Luxury Package",
                "price": 5000,
                "activities": ["Spa treatments", "Fine dining", "Wine tasting"]
            }
        ]
    }
}

POLICIES = {
    "cancellation": {
        "title": "Cancellation Policy",
        "description": "Flexible cancellation options based on advance notice",
        "tiers": [
            {
                "days_before": "30+",
                "refund_percentage": 100,
                "description": "Full refund"
            },
            {
                "days_before": "14-30",
                "refund_percentage": 75,
                "description": "75% refund"
            },
            {
                "days_before": "7-14",
                "refund_percentage": 50,
                "description": "50% refund"
            },
            {
                "days_before": "Less than 7",
                "refund_percentage": 25,
                "description": "25% refund"
            },
            {
                "days_before": "0 (No show)",
                "refund_percentage": 0,
                "description": "No refund"
            }
        ]
    },
    "group_discounts": {
        "title": "Group Booking Discounts",
        "tiers": [
            {"group_size": "10-20", "discount": "5%"},
            {"group_size": "20-50", "discount": "10%"},
            {"group_size": "50+", "discount": "15% + free activity"}
        ]
    },
    "guarantee": {
        "title": "MKOV Guarantee",
        "promises": [
            "Best price guarantee",
            "24/7 traveler support",
            "Travel insurance included",
            "Hassle-free refunds",
            "Expert travel consultants"
        ]
    }
}

CONTACT = {
    "phone": "+91-120-XXXXXX",
    "email": "support@uniglobemkov.in",
    "address": "Noida, Uttar Pradesh, India",
    "hours": {
        "weekday": "9:00 AM - 9:00 PM",
        "weekend": "10:00 AM - 6:00 PM"
    }
}
