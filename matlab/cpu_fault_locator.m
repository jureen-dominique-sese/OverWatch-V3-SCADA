function report = cpu_fault_locator(sensor_readings)
% CPU_FAULT_LOCATOR
% The "Brain" of the system.
% Input: Matrix of currents from all units [Unit1_ABC; Unit2_ABC; ...]

    %% 0. INITIALIZE OUTPUT STRUCTURE
    % We define default values so the script never crashes if no fault is found.
    report.status = 'No Fault Detected';
    report.type = 'N/A';
    report.location = 0;
    report.closest_unit = 0;
    report.measured_amps = 0;

    % Load the "Cheat Sheet"
    if ~isfile('Fault_Lookup_Table.mat')
        error('Lookup Table not found! Run generate_database.m first.');
    end
    load('Fault_Lookup_Table.mat', 'data_SLG', 'data_LL', 'data_3PH');
    sys = get_system_config();
    
    %% STEP 1: ZONE IDENTIFICATION
    % Find the furthest unit that saw the fault.
    last_active_unit_idx = 0;
    measured_currents = [0, 0, 0];
    
    num_units = size(sensor_readings, 1);
    
    for i = 1:num_units
        % Check max current on this unit
        I_max = max(sensor_readings(i, :));
        
        % Threshold to decide if unit is "Tripped" (e.g. > 50 Amps)
        if I_max > 50 
            last_active_unit_idx = i;
            measured_currents = sensor_readings(i, :); % Capture this reading
        end
    end
    
    % If no unit tripped, return the default "No Fault" report immediately
    if last_active_unit_idx == 0
        return; 
    end
    
    % Define the Search Zone
    min_search_dist = sys.unit_locations_km(last_active_unit_idx);
    
    
    %% STEP 2: FAULT TYPE CLASSIFICATION
    % Use the ratios of Ia, Ib, Ic from the active unit
    Ia = measured_currents(1);
    Ib = measured_currents(2);
    Ic = measured_currents(3);
    I_peak = max(measured_currents);
    
    search_table = [];
    target_val = 0;
    col_idx = 0;
    
    % Logic to identify type and select the correct column for lookup
    if (Ia > 0.5*I_peak) && (Ib < 0.2*I_peak) && (Ic < 0.2*I_peak)
        % SLG (Phase A)
        search_table = data_SLG;
        report.type = 'Single Line-to-Ground (Phase A)';
        target_val = Ia; 
        col_idx = 2;     % Column 2 is Ia in our DB
        
    elseif (Ia < 0.2*I_peak) && (Ib > 0.8*I_peak) && (Ic > 0.8*I_peak)
        % LL (Phase B-C)
        search_table = data_LL;
        report.type = 'Line-to-Line (Phase B-C)';
        target_val = Ib; 
        col_idx = 3;     % Column 3 is Ib
        
    elseif (Ia > 0.9*I_peak) && (Ib > 0.9*I_peak) && (Ic > 0.9*I_peak)
        % 3PH
        search_table = data_3PH;
        report.type = 'Three-Phase Balanced';
        target_val = Ia;
        col_idx = 2;
        
    else
        % Fallback for messy data
        search_table = data_SLG;
        report.type = 'Uncertain (Defaulting to SLG)';
        target_val = I_peak;
        col_idx = 2;
    end
    
    %% STEP 3: PINPOINT LOCATION (Inverse Lookup)
    % We filter the table to only look at distances > min_search_dist
    
    valid_rows = search_table(:, 1) >= min_search_dist;
    filtered_table = search_table(valid_rows, :);
    
    % Find row with closest current match
    theoretical_vals = filtered_table(:, col_idx);
    [min_diff, idx] = min(abs(theoretical_vals - target_val));
    
    best_match_row = filtered_table(idx, :);
    estimated_dist = best_match_row(1);
    
    %% UPDATE OUTPUT REPORT
    report.status = 'FAULT CONFIRMED';
    report.location = estimated_dist;
    report.closest_unit = last_active_unit_idx;
    report.measured_amps = target_val;
end