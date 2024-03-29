import numpy as np
import rospy
import dynamic_reconfigure.client
from panda_ros import Panda
from panda_ros.pose_transform_functions import array_quat_2_pose, pose_2_transformation, orientation_2_quaternion, list_2_quaternion
from geometry_msgs.msg import PoseStamped
from quaternion_algebra.algebra import quaternion_divide, to_euler_angles, from_euler_angles, quaternion_product
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Vector3
class MassEstimator(Panda):
    def __init__(self):
        rospy.init_node("mass_estimator_node")
        super(MassEstimator, self).__init__()
        self.set_mass = dynamic_reconfigure.client.Client('/dynamic_reconfigure_mass_param_node', config_callback=None)
        self.goal_sub = rospy.Subscriber('/equilibrium_pose', PoseStamped, self.ee_pos_goal_callback)
        self.marker_pub = rospy.Publisher('/camera_mass', Marker, queue_size=0)
        rospy.sleep(1)    
        self.estimated_mass=200
        self.estimated_offset_x=40
        self.estimated_offset_y=20
        self.estimated_offset_z=-50
    def visualize_mass(self):
        # Create a marker message
        marker = Marker()
        marker.header.frame_id = "panda_EE"
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.scale = Vector3(self.estimated_mass * 100000, self.estimated_mass * 100000, self.estimated_mass* 100000)  # Dimensions of the ellipsoid
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
        marker.color.a = 0.8

        # Set the position and orientation of the ellipsoid
        marker.pose.position.x = self.estimated_offset_x*10000
        marker.pose.position.y = self.estimated_offset_y*10000
        marker.pose.position.z = self.estimated_offset_z*10000
        marker.pose.orientation.x = 0.0
        marker.pose.orientation.y = 0.0
        marker.pose.orientation.z = 0.0
        marker.pose.orientation.w = 1.0

        print("publish marker")
        # Publish the marker
        self.marker_pub.publish(marker)

        
    def set_nullspace(self):
        self.set_configuration(self.curr_joint)
    def esitmate_mass(self):
        K_x = self.set_K.update_configuration({})['translational_stiffness_X']
        # print("K_x", K_x)
        self.estimated_mass=self.estimated_mass+np.floor(np.clip((self.curr_pos_goal[2]-self.curr_pos[2])*K_x*10, -30, 30))
        # self.estimated_mass=self.estimated_mass+np.sign(self.curr_pos_goal[2]-self.curr_pos[2])*2
        self.set_mass.update_configuration({"mass": self.estimated_mass})
        self.visualize_mass()
    def estimate_offset_plane(self):    
        K_x = self.set_K.update_configuration({})['translational_stiffness_X'] *1
        curr_quat= list_2_quaternion(self.curr_ori)
        curr_pose= array_quat_2_pose(self.curr_pos, curr_quat)
        curr_tranformation= pose_2_transformation(curr_pose.pose)
        orientation_matrix_transpose= np.transpose(curr_tranformation[0:2,:])
        goal_quat = list_2_quaternion(self.curr_ori_goal)
        quat_diff= quaternion_divide(goal_quat, curr_quat ) # goal-curr
        euler= to_euler_angles(quat_diff)

        gradient= orientation_matrix_transpose @ np.array([euler[1], - euler[0]])
        # self.estimated_mass=self.estimated_mass+np.floor(np.clip((self.curr_pos_goal[2]-self.curr_pos[2])*K_x*10, -30, 30))
        self.estimated_offset_x=self.estimated_offset_x- np.clip(gradient[0]* self.estimated_mass *10, -10, 10)
        self.estimated_offset_y=self.estimated_offset_y- np.clip(gradient[1]* self.estimated_mass * 10, -10, 10)
        # self.estimated_offset_z=self.estimated_offset_z-np.sign(gradient[2])
        # self.set_mass.update_configuration({"mass": self.estimated_mass})
        self.set_mass.update_configuration({"offset_x": self.estimated_offset_x})
        self.set_mass.update_configuration({"offset_y": self.estimated_offset_y})
        self.visualize_mass()

    def estimate_offset_vertical(self):
        curr_quat= list_2_quaternion(self.curr_ori)
        curr_pose= array_quat_2_pose(self.curr_pos, curr_quat)
        curr_tranformation= pose_2_transformation(curr_pose.pose)
        orientation_matrix_transpose= np.transpose(curr_tranformation[0:2,:])
        goal_quat = list_2_quaternion(self.curr_ori_goal)
        quat_diff= quaternion_divide(goal_quat, curr_quat ) # goal-curr
        euler= to_euler_angles(quat_diff)

        gradient= orientation_matrix_transpose @ np.array([euler[1], - euler[0]])
        # self.estimated_offset_x=self.estimated_offset_x-np.sign(gradient[0])
        # self.estimated_offset_y=self.estimated_offset_y-np.sign(gradient[1])
        self.estimated_offset_z=self.estimated_offset_z- np.clip(gradient[2]* self.estimated_mass *10, -10, 10)
        # self.set_mass.update_configuration({"offset_x": self.estimated_offset_x})
        # self.set_mass.update_configuration({"offset_y": self.estimeated_offset_y})
        self.set_mass.update_configuration({"offset_z": self.estimatd_offset_z})
        self.visualize_mass()



        

if __name__ == '__main__':

    Estimator=MassEstimator()
    Estimator.home()
    n=40
    amplitude = 30/180*np.pi
    t = np.linspace(0, 2 * np.pi, n)  # Create 'n' evenly spaced points from 0 to 2*pi
    sine_wave_values = amplitude * np.sin(t)
    quat_start=list_2_quaternion(Estimator.curr_ori_goal)
    pos_start=Estimator.curr_pos_goal
    Estimator.set_configuration(Estimator.curr_joint)
    Estimator.set_stiffness(4000,4000,4000,100,100,100,0)
    print("goal quat")
    print(quat_start)
    #Estimator.offset_compensator(30)
    for _ in range (60):
        Estimator.esitmate_mass()
        rospy.sleep(1)
    for _ in range (60):
        Estimator.estimate_offset_plane()
        rospy.sleep(1)    
        
    # #TEST
    # quat_diff=from_euler_angles(0, 0, -45/180*np.pi)
    # quat=quaternion_product(quat_diff, quat_start )
    # goal_pose = array_quat_2_pose(Estimator.curr_pos_goal, quat)
    # Estimator.go_to_pose(goal_pose)
    # print("goal pose")
    # print(goal_pose)
    # rospy.sleep(10)
    
    # quat_diff=from_euler_angles(0, 0, -90/180*np.pi)
    # quat=quaternion_product(quat_diff, quat_start )
    # goal_pose = array_quat_2_pose(Estimator.curr_pos_goal, quat)
    # Estimator.go_to_pose(goal_pose)
    # print("goal pose")
    # print(goal_pose)
    # rospy.sleep(10)
        
        
    '''    
    quat_diff=from_euler_angles(-60/180*np.pi, 0, 0)
    quat=quaternion_product(quat_diff, quat_start )
    goal_pose = array_quat_2_pose(Estimator.curr_pos_goal, quat)
    Estimator.set_stiffness(100,100,100,2,2,2,0)
    Estimator.go_to_pose(goal_pose)
    Estimator.set_configuration(Estimator.curr_joint)
    Estimator.set_stiffness(100,100,100,2,2,2,0)
    print("goal pose")
    print(goal_pose)
    for _ in range (60):
        Estimator.estimate_offset_vertical()
        rospy.sleep(1)

    quat_diff=from_euler_angles(60/180*np.pi, 0, 0)
    quat=quaternion_product(quat_diff, quat_start )
    goal_pose = array_quat_2_pose(Estimator.curr_pos_goal, quat)
    #Estimator.set_stiffness(1000,1000,1000,20,20,20,0)
    Estimator.go_to_pose(goal_pose)
    Estimator.set_configuration(Estimator.curr_joint)
    print("goal pose")
    print(goal_pose)
    #Estimator.set_stiffness(1000,1000,1000,20,20,20,0.2)
    for _ in range (40):
        Estimator.estimate_offset_vertical()
        rospy.sleep(1)    
   
    # for i in range(n):
    #     print(sine_wave_values[i])
    #     quat_diff=from_euler_angles(sine_wave_values[i], sine_wave_values[i], 0)
    #     quat=quaternion_product(quat_diff, quat_start )
    #     goal_pose = array_quat_2_pose(Estimator.curr_pos_goal, quat)
    #     Estimator.go_to_pose(goal_pose)
    #     rospy.sleep(0.5)
    #     for _ in range (20):
    #         rospy.sleep(0.05)
    #         Estimator.estimate_offset()
    '''

