import re
from typing import List, Dict
from datetime import datetime


class LogParser:
    @staticmethod
    def extract_errors(log_text: str) -> List[str]:
        error_pattern = r'(ERROR|EXCEPTION|CRITICAL|FATAL).*'
        errors = re.findall(error_pattern, log_text, re.IGNORECASE)
        return errors[:50]
    
    @staticmethod
    def extract_timestamps(log_text: str) -> List[str]:
        timestamp_pattern = r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'
        timestamps = re.findall(timestamp_pattern, log_text)
        return timestamps
    
    @staticmethod
    def extract_stack_traces(log_text: str) -> List[str]:
        traces = []
        lines = log_text.split('\n')
        
        in_trace = False
        current_trace = []
        
        for line in lines:
            if 'Traceback' in line or 'Stack trace' in line:
                in_trace = True
                current_trace = [line]
            elif in_trace:
                if line.strip().startswith('at ') or line.strip().startswith('File '):
                    current_trace.append(line)
                elif line.strip() == '':
                    if current_trace:
                        traces.append('\n'.join(current_trace))
                        current_trace = []
                    in_trace = False
        
        return traces[:10]
