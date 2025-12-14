function [sensor_data, max_noise_pct] = simulate_overwatch_network(actual_fault_dist, actual_fault_type)
% SIMULATE_OVERWATCH_NETWORK
% Returns: sensor_data, and the Maximum Noise % applied in this specific trial.

    sys = get_system_config();
    unit_locs = sys.unit_locations_km;
    num_units = length(unit_locs);
    
    I_fault_vector = calculate_fault_current(actual_fault_dist, actual_fault_type, 0);
    readings = zeros(num_units, 3);
    
    % --- NOISE CONFIGURATION ---
    % Using specific deviation data (5.0A ref)
    std_amps = 0; % Update this every now and then
    SENSOR_STD = std_amps / 5.0; 
    
    max_noise_pct = 0; % Track the worst noise in this specific run

    for i = 1:num_units
        u_dist = unit_locs(i);
        
        if u_dist < actual_fault_dist
            % UPSTREAM
            % Generate random noise vector
            raw_noise = SENSOR_STD * randn(1, 3);
            noise_factors = 1 + raw_noise;
            
            % Capture the max absolute noise % for reporting
            current_max = max(abs(raw_noise)) * 100;
            if current_max > max_noise_pct
                max_noise_pct = current_max;
            end
            
            readings(i, :) = I_fault_vector.' .* noise_factors;
        else
            % DOWNSTREAM
            readings(i, :) = [0, 0, 0]; 
        end
    end
    
    sensor_data.readings = readings;
    sensor_data.unit_locs = unit_locs;
end