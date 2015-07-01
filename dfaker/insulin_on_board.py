from datetime import datetime, timedelta 

from . import tools

def format_bolus_for_iob_calc(bolus_data):
    """ Retrieve rates, times and duration values from bolus data to generate IOB values
        Returns a list of time-bolus lists
    """ 
    time_vals = []
    for bolus_entry in bolus_data:
        str_time = bolus_entry["time"]
        timestamp = tools.convert_ISO_to_epoch(str_time, '%Y-%m-%dT%H:%M:%S.000Z')
        if bolus_entry['subType'] == "normal":
            initial_insulin = bolus_entry["normal"]
            time_vals.append([timestamp, initial_insulin])
        else:
            duration = bolus_entry["duration"]/1000/60 #in minutes
            if duration > 0:
                num_segments = duration / 5 #5 minute segments 
                extended_insulin = bolus_entry["extended"]
                insulin_per_segment = extended_insulin / num_segments
                if bolus_entry['subType'] == "dual/square":
                    initial_insulin = bolus_entry["normal"]
                    time_vals.append([timestamp, initial_insulin])
                next_time = timestamp 
                end_time = next_time + duration*60 #duration in seconds
                while next_time < end_time:
                    time_vals.append([next_time, insulin_per_segment])
                    next_time += 5 * 60 #next time -- 5 minutes later (in seconds)  
    return time_vals            
        
def create_iob_dict(bolus_data, action_time):
    """ Return a dictionary with insulin on board values for every timestamp in bolus_data
        bolus_data -- a list of dict enteries generated when running the bolus module
        action_time -- an integer representing number of hours it takes insulin to leave the body
    """
    time_vals = format_bolus_for_iob_calc(bolus_data)
    iob_dict = {}
    for time_bolus in time_vals:
        remaining_time = action_time * 60 #in minutes
        step = 0 
        time = time_bolus[0]
        initial_value = time_bolus[1]
        slope = initial_value / action_time
        iob_dict = add_iob(iob_dict, time, initial_value, slope, step)
        while remaining_time > 5: #continue to calculate iob values until complete decay
            step += float(5/60) #5 min in hours
            time += 5 * 60 
            iob_dict = add_iob(iob_dict, time, initial_value, slope, step)
            remaining_time -= 5 #subtract 5 minutes from remaining time 
    return iob_dict

def add_iob(curr_dict, time, initial_value, slope, step):
    """ Add a single iob amount to the iob_dict based on linear decay equation"""
    iob_amount = initial_value - slope * step #linear decay equation to calculate IOB at any time 
    if time not in curr_dict:
        curr_dict[time] = iob_amount
    else: 
        curr_dict[time] += iob_amount
    return curr_dict

def update_iob_dict(curr_dict, associated_bolus, action_time):
    """ After a new bolus events is generated during a wizard event, update the iob_dict"""
    to_add = create_iob_dict(associated_bolus, action_time)
    for key in to_add:
        if key in curr_dict:
            curr_dict[key] += to_add[key]
        else:
            curr_dict[key] = to_add[key]
    return curr_dict    

def insulin_on_board(iob_dict, timestamp):
    """ Return insulin on board for a particular timestamp (possible error up to 5 minutes)
        If a timestamp matches an entry in the iob_dict, return that exact value,
        else find the closest timestamp and if it is within 5 minutes, use that value
        else return 0 as the insulin_on_board value 
    """
    if iob_dict:
        if timestamp in iob_dict:
            return iob_dict[timestamp]
        closest_timestamp = min(iob_dict.keys(), key=lambda k: abs(k-timestamp))
        if abs(timestamp - closest_timestamp) <= 300: #approximate to 5 minutes max
            return iob_dict[closest_timestamp]
    return 0