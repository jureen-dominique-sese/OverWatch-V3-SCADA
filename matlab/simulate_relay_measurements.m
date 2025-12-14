function [V_relay, I_relay] = simulate_relay_measurements(fault_dist, fault_type)
% SIMULATE_RELAY_MEASUREMENTS
% Calculates what voltage and current the relay at substation sees
%
% This simulates the electrical measurements at distance = 0 (substation)

    sys = get_system_config();
    
    % Calculate fault current (we already have this)
    I_fault_pu = calculate_fault_current(fault_dist, fault_type, 0);
    
    % For impedance method, we need the PHASE A current in complex form
    % Our calculate_fault_current returns magnitude only, so we reconstruct
    
    % Recalculate with complex values
    Z1_total = sys.Z_source + (sys.z1_pu_km * fault_dist);
    Z2_total = Z1_total;
    Z0_total = sys.Z_source + (sys.z0_pu_km * fault_dist);
    
    V_f = 1.0;  % Pre-fault voltage (pu)
    
    % Get sequence currents (complex)
    if fault_type == 1  % SLG
        I1 = V_f / (Z1_total + Z2_total + Z0_total);
        I2 = I1;
        I0 = I1;
    elseif fault_type == 2  % LL
        I1 = V_f / (Z1_total + Z2_total);
        I2 = -I1;
        I0 = 0;
    elseif fault_type == 3  % 3PH
        I1 = V_f / Z1_total;
        I2 = 0;
        I0 = 0;
    end
    
    % Voltage at relay point during fault
    % V_relay = V_prefault - I * Z_line_to_fault
    Z_line_to_fault = sys.z1_pu_km * fault_dist;
    V_relay = V_f - (I1 * Z_line_to_fault);
    
    % Current at relay (use phase A)
    a = -0.5 + 1j*0.866;
    I_phase_pu = I0 + I1 + I2;  % Phase A in sequence components
    
    % Return complex values
    I_relay = I_phase_pu;  % Complex current (pu)
    % V_relay already calculated above (complex pu)
    
end