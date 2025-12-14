%% OVERWATCH SIMULATION - MASTER RUNNER
clear; clc;

% --- INPUTS (Change these to test!) ---
TEST_FAULT_LOC_KM = 8;   % Let's put a fault at 6.45 km
TEST_FAULT_TYPE = 1;        % 1=SLG (Phase A)

fprintf('========================================\n');
fprintf('       OVERWATCH SYSTEM SIMULATION      \n');
fprintf('========================================\n');

% 1. SIMULATE THE PHYSICAL WORLD
% This generates the currents that the sensors would physically see.
fprintf('1. Simulating Physical Fault at %.2f km...\n', TEST_FAULT_LOC_KM);
sensor_data = simulate_overwatch_network(TEST_FAULT_LOC_KM, TEST_FAULT_TYPE);

% Display what the sensors see (optional debugging)
disp('   Sensor Readings (Amps):');
disp(sensor_data.readings);

% 2. RUN THE CPU ALGORITHM
% The CPU takes ONLY the sensor_data.readings (it doesn't know the location!)
fprintf('2. Transmitting Data to Central CPU...\n');
result = cpu_fault_locator(sensor_data.readings);

% 3. DISPLAY RESULTS
fprintf('\n---------------- RESULT ----------------\n');
fprintf('STATUS:           %s\n', result.status);
fprintf('DETECTED TYPE:    %s\n', result.type);
fprintf('ESTIMATED LOC:    %.3f km\n', result.location);
fprintf('ACTUAL LOC:       %.3f km\n', TEST_FAULT_LOC_KM);

error_m = abs(result.location - TEST_FAULT_LOC_KM) * 1000;
fprintf('ACCURACY ERROR:   %.2f meters\n', error_m);
fprintf('----------------------------------------\n');

% 4. EXPORT FOR PYTHON GUI (Optional)
% We save the result to a CSV so your Python map can read it.
csv_header = {'Unit1_Amp','Unit2_Amp','Unit3_Amp','Est_Lat','Est_Long'};
% (For now, just saving the raw output)
save('sim_output.mat', 'result');
fprintf('Data exported for GUI.\n');