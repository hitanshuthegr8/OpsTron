import logging
from twilio.rest import Client
from typing import Optional
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

class TwilioService:
    """
    Handles outbound voice alerts using Twilio Programmable Voice.
    
    Used to wake up/alert developers when critical errors or 
    deployment regressions occur.
    """
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.to_number = settings.ALERT_PHONE_NUMBER
        
        self.is_configured = all([
            self.account_sid, 
            self.auth_token, 
            self.from_number, 
            self.to_number
        ])
        
        if self.is_configured:
            try:
                self.client = Client(self.account_sid, self.auth_token)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                self.is_configured = False
        else:
            logger.warning("Twilio is not fully configured. Voice alerts will be disabled.")
            
    def send_voice_alert(self, message: str) -> bool:
        """
        Places a phone call and reads the provided message using TwiML.
        
        Args:
            message (str): The text to be spoken to the user.
            
        Returns:
            bool: True if call was successfully initiated, False otherwise.
        """
        if not self.is_configured:
            logger.warning(f"Voice alert skipped (Twilio not configured): {message}")
            return False
            
        try:
            # We use Twilio's TwiML (XML) to instruct the call to speak the message
            # The pause gives the user time to put the phone to their ear after answering
            twiml = f'''
            <Response>
                <Pause length="1"/>
                <Say voice="Polly.Matthew-Neural">{message}</Say>
                <Pause length="1"/>
                <Say voice="Polly.Matthew-Neural">Goodbye.</Say>
            </Response>
            '''
            
            call = self.client.calls.create(
                to=self.to_number,
                from_=self.from_number,
                twiml=twiml
            )
            
            logger.info(f"Initiated Twilio voice alert (Call SID: {call.sid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Twilio voice alert: {e}")
            return False
