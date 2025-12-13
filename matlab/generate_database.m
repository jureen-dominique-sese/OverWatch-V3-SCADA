function generate_database()
% GENERATE_DATABASE
% Creates 'Fault_Lookup_Table.mat'
% Simulates faults every 10 meters (0.01km) to create the Ground Truth.

    fprintf('Generating Theoretical Data... ');
    
    max_len = 10.0; % 10 km line
    step = 0.01;    % 10 meter resolution
    distances = step:step:max_len;
    
    % Initialize Tables
    % Columns: [Distance_km, Ia, Ib, Ic]
    data_SLG = [];
    data_LL = [];
    data_3PH = [];
    
    for d = distances
        % 1. Simulate SLG
        I_slg = calculate_fault_current(d, 1, 0);
        data_SLG = [data_SLG; d, I_slg(1), I_slg(2), I_slg(3)];
        
        % 2. Simulate LL
        I_ll = calculate_fault_current(d, 2, 0);
        data_LL = [data_LL; d, I_ll(1), I_ll(2), I_ll(3)];
        
        % 3. Simulate 3PH
        I_3ph = calculate_fault_current(d, 3, 0);
        data_3PH = [data_3PH; d, I_3ph(1), I_3ph(2), I_3ph(3)];
    end
    
    % Save specific variables
    save('Fault_Lookup_Table.mat', 'data_SLG', 'data_LL', 'data_3PH');
    fprintf('Done! Database Saved.\n');
end