function [V_relay, I_relay] = simulate_relay_measurements(fault_dist, fault_type)
% SIMULATE_RELAY_MEASUREMENTS
% Now with 1% NOISE to match the Lookup Table tests.

    sys = get_system_config();
    
    % --- 1. CALCULATE PERFECT VALUES FIRST ---
    Z1_line = sys.z1_pu_km * fault_dist;
    Z0_line = sys.z0_pu_km * fault_dist;
    
    Z1_total = sys.Z_source + Z1_line;
    Z2_total = Z1_total;
    Z0_total = sys.Z_source + Z0_line;
    
    V_f = 1.0;
    
    % Sequence Currents
    if fault_type == 1  % SLG
        I1 = V_f / (Z1_total + Z2_total + Z0_total);
        I2 = I1; I0 = I1;
    elseif fault_type == 2  % LL
        I1 = V_f / (Z1_total + Z2_total);
        I2 = -I1; I0 = 0;
    elseif fault_type == 3  % 3PH
        I1 = V_f / Z1_total;
        I2 = 0; I0 = 0;
    end
    
    % Perfect Relay Quantities
    if fault_type == 2
        % LL (Phase B)
        a = exp(1j*2*pi/3);
        I_perfect = I0 + a^2*I1 + a*I2; 
        
        I1_b = a^2 * I1; I2_b = a * I2; I0_b = I0;
        V_perfect = (I1_b * Z1_line) + (I2_b * Z1_line) + (I0_b * Z0_line);
    else
        % SLG/3PH (Phase A)
        I_perfect = I0 + I1 + I2;
        V_perfect = (I1 * Z1_line) + (I2 * Z1_line) + (I0 * Z0_line);
    end
    
    % --- 2. INJECT REALISTIC SENSOR NOISE ---
    % Add +/- 1% error magnitude and slight phase shift error
    % This represents CT and PT inaccuracy (Class 1.0 sensors)
    
    noise_mag_V = 1 + (0.01 * (2*rand() - 1)); % +/- 1% Magnitude
    noise_mag_I = 1 + (0.01 * (2*rand() - 1)); 
    
    % Optional: Add tiny phase error (e.g., +/- 0.5 degrees)
    % noise_ph_V = exp(1j * (0.5 * pi/180 * (2*rand() - 1)));
    
    V_relay = V_perfect * noise_mag_V;
    I_relay = I_perfect * noise_mag_I;
    
end