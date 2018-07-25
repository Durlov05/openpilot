import numpy as np
from cereal import car
from common.kalman.simple_kalman import KF1D
from selfdrive.config import Conversions as CV
from selfdrive.can.parser import CANParser
from selfdrive.car.subaru.values import DBC, CAR

def get_powertrain_can_parser(CP, canbus):
  # this function generates lists for signal, messages and initial values
  signals = [
    # sig_name, sig_address, default
    ("LEFT_BLINKER", "Dashlights", 0), 
    ("RIGHT_BLINKER", "Dashlights", 0),
    ("Cruise_Activated", "ES_Status", 0),
    ("Steering_Angle", "Steering", 0),
    ("FL", "WHEEL_SPEEDS", 0), 
    ("FR", "WHEEL_SPEEDS", 0),
    ("RL", "WHEEL_SPEEDS", 0), 
    ("RR", "WHEEL_SPEEDS", 0), 
    ("Message", "WHEEL_SPEEDS", 0), 
    ("Steer_Torque_Sensor", "Steering_Torque", 0),
    ("Cruise_On", "ES_Status", 0),
    ("Message", "ES_Status", 0),
    ("Message", "ES_Brake", 0),
    ("Message", "ES_RPM", 0),
    ("Message", "ES_LDW", 0),
    ("Message", "ES_CruiseThrottle", 0),
  ]
  
  checks = [
    # sig_address, frequency
    ("Dashlights", 10),
    ("ES_Status", 20),
    ("ES_Brake", 20),
    ("ES_RPM", 20),
    ("ES_LDW", 20),
    ("ES_CruiseThrottle", 20),
    ("Steering", 100),
    ("WHEEL_SPEEDS", 50),
    ("Steering_Torque", 100),
  ]

  return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, canbus.powertrain)
  
class CarState(object):
  def __init__(self, CP, canbus):
    # initialize can parser

    self.car_fingerprint = CP.carFingerprint
    self.left_blinker_on = False
    self.prev_left_blinker_on = False
    self.right_blinker_on = False
    self.prev_right_blinker_on = False
    #FIXME
    self.steer_torque_driver = 0
    self.steer_not_allowed = False
    self.main_on = False
    self.es_status = 0
    self.es_brake = 0
    self.es_rpm = 0
    self.es_ldw = 0
    self.es_cruisethrottle = 0
    # vEgo kalman filter
    dt = 0.01
    self.v_ego_kf = KF1D(x0=np.matrix([[0.], [0.]]),
                         A=np.matrix([[1., dt], [0., 1.]]),
                         C=np.matrix([1., 0.]),
                         K=np.matrix([[0.12287673], [0.29666309]]))
    self.v_ego = 0.

  def update(self, pt_cp):

    self.can_valid = pt_cp.can_valid
    self.can_valid = True
    
    self.v_wheel_fl = pt_cp.vl["WHEEL_SPEEDS"]['FL'] * CV.KPH_TO_MS
    self.v_wheel_fr = pt_cp.vl["WHEEL_SPEEDS"]['FR'] * CV.KPH_TO_MS
    self.v_wheel_rl = pt_cp.vl["WHEEL_SPEEDS"]['RL'] * CV.KPH_TO_MS
    self.v_wheel_rr = pt_cp.vl["WHEEL_SPEEDS"]['RR'] * CV.KPH_TO_MS
    speed_estimate = (self.v_wheel_fl + self.v_wheel_fr + self.v_wheel_rl + self.v_wheel_rr) / 4.0
    #print("speed_estimate")
    #print(speed_estimate)

    self.v_ego_raw = speed_estimate
    # FIXME
    v_ego_x = self.v_ego_kf.update(speed_estimate)
    self.v_ego = float(v_ego_x[0])
    self.a_ego = float(v_ego_x[1])
    #self.v_ego = speed_estimate
    #self.a_ego = speed_estimate

    #print(self.v_ego_raw)
    #print(self.v_ego)
    #print(self.a_ego)

    self.standstill = self.v_ego_raw < 0.01

    self.angle_steers = pt_cp.vl["Steering"]['Steering_Angle']
    self.steer_override = abs(self.steer_torque_driver) > 500.0

    self.prev_left_blinker_on = self.left_blinker_on
    self.prev_right_blinker_on = self.right_blinker_on
    self.left_blinker_on = pt_cp.vl["Dashlights"]['LEFT_BLINKER'] == 1
    self.right_blinker_on = pt_cp.vl["Dashlights"]['RIGHT_BLINKER'] == 1

    if self.car_fingerprint == CAR.OUTBACK:
      self.acc_active = pt_cp.vl["ES_Status"]['Cruise_Activated']
      self.main_on = pt_cp.vl["ES_Status"]['Cruise_On']
      self.steer_torque_driver = pt_cp.vl["Steering_Torque"]['Steer_Torque_Sensor']
      self.steer_override = abs(self.steer_torque_driver) > 2500.0
      #Forwarding attempt
      self.es_status = pt_cp.vl["ES_Status"]['Message']
      self.es_brake = pt_cp.vl["ES_Brake"]['Message']
      self.es_rpm = pt_cp.vl["ES_RPM"]['Message']
      self.es_ldw = pt_cp.vl["ES_LDW"]['Message']
      self.es_cruisethrottle = pt_cp.vl["ES_CruiseThrottle"]['Message']
      self.wheel_speeds = pt_cp.vl["WHEEL_SPEEDS"]['Message']

    if self.car_fingerprint == CAR.XV2018:
      self.acc_active = pt_cp.vl["ES_Status"]['Cruise_Activated']
      self.main_on = pt_cp.vl["ES_Status"]['Cruise_Activated']
      self.steer_override = abs(self.steer_torque_driver) > 500.0
      
