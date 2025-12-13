function sensor_data = simulate_overwatch_network(actual_fault_dist, actual_fault_type)
% SIMULATE_OVERWATCH_NETWORK
% Generates the readings for all Overwatch units based on a specific fault.
% NOW INCLUDES: +/- 1% Sensor Noise

    % 1. Load System Config to get Unit Locations
    sys = get_system_config();
    unit_locs = sys.unit_locations_km;
    num_units = length(unit_locs);
    
    % 2. Calculate the Fault Current at the epicenter
    % We use the engine we built earlier
    % Hardcoded 0 ohms for Rf as per your previous version
    I_fault_vector = calculate_fault_current(actual_fault_dist, actual_fault_type, 0);
    
    % 3. Determine what each unit sees (The Radial Logic)
    readings = zeros(num_units, 3);
    
    % Define Noise Level (1% = 0.01)
    NOISE_LIMIT = 0.01; 
    
    for i = 1:num_units
        u_dist = unit_locs(i);
        
        if u_dist < actual_fault_dist
            % Unit is UPSTREAM of the fault -> It sees the fault current
            
            % --- NOISE INJECTION START ---
            % Generate random noise for 3 phases: Range [-1% to +1%]
            % Formula: (2*rand - 1) gives range [-1, 1]
            noise_factors = 1 + (NOISE_LIMIT * (2*rand(1, 3) - 1));
            
            % Apply noise to the perfect vector
            % FIX: Transpose I_fault_vector (3x1) to (1x3) to match noise_factors
            readings(i, :) = I_fault_vector.' .* noise_factors;
            % --- NOISE INJECTION END ---
            
            status = 'ACTIVE'; % Kept for consistency with your snippet
        else
            % Unit is DOWNSTREAM -> It sees 0 (or negligible load)
            readings(i, :) = [0, 0, 0]; 
            status = 'IDLE';   % Kept for consistency with your snippet
        end
    end
    
    sensor_data.readings = readings;
    sensor_data.unit_locs = unit_locs;
end