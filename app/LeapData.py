import sys
import re
import numpy as np
import pandas

from config.Skeleton import Skeleton
from resources.pymo.pymo.data import MocapData
from RotationUtil import rot2eul, vec2eul, get_order
from resources.LeapSDK.v4_python37 import Leap


class LeapData:
    """
    A class to convert LeapMotion frames to PyMO data structure (MocapData)

    Calculates translations (offsets) and rotation data for the joints
    """

    def __init__(self, channel_setting='rotation'):
        self._skeleton = {}
        self._setting = Skeleton(channel_setting)
        self._motion_channels = []
        self._motions = []
        self._framerate = 0.0
        self._root_name = ''
        self.data = MocapData()

        self.first_frame = None

        self._skeleton = self._setting.skeleton
        # fill channels into skeleton in selected order (i.e. xyz)
        self._skeleton_apply_channels(self._setting.channel_setting)

        self._root_name = self._setting.root_name
        self._framerate = self._setting.framerate  # TODO: framerate

        for key, value in self._skeleton.items():
            value['offsets'] = [0, 0, 0]
            for channel in value['channels']:
                self._motion_channels.append((key, channel))

    def parse(self):
        self.data.skeleton = self._skeleton
        self.data.channel_names = self._motion_channels
        self.data.values = self._motion2DataFrame()
        self.data.root_name = self._root_name
        self.data.framerate = self._framerate

        return self.data

    def _check_frame(self, frame):
        """
        Check whether frame and hand and fingers are valid, produce error when left hand is shown
        """
        if frame.hands.is_empty:
            print("No hand found.")
            return False

        # Get the first hand
        hand = frame.hands[0]

        if hand.is_left:
            # sys.stdout.write("\rPlease use your right hand")
            print("Please use your right hand.")
            sys.stdout.flush()
            return False

        if not hand.is_right and not hand.is_valid:
            return False

        # sys.stdout.write("\rValid right hand found, recording data. Current frame: {}"
        #                  .format(self.actual_frame))

        # Check if the hand has any fingers
        fingers = hand.fingers
        if fingers.is_empty:
            print("No valid fingers found.")
            return False

        # TODO
        frame_number = 0 if not self.first_frame else frame.id - self.first_frame.id
        print("Valid right hand found, recording data. Current frame: {}".format(frame_number))
        # sys.stdout.flush()
        return True

    def add_frame(self, frame):
        if not self._check_frame(frame):
            return

        # Get the first hand
        hand = frame.hands[0]
        if not self.first_frame:
            self.first_frame = frame
            channel_values = self._get_channel_values(hand, firstframe=True)
            self._motions.append((0, channel_values))
            return

        channel_values = self._get_channel_values(hand)
        self._motions.append((frame.timestamp - self.first_frame.timestamp, channel_values))

    def _get_channel_values(self, hand, firstframe=False):
        channel_values = []
        for joint_name, joint_value in self._skeleton.items():
            # motion data with rotations
            if joint_name == self._root_name:
                x_pos, y_pos, z_pos = LeapData._get_root_offset()
            elif joint_name == 'RightElbow':
                x_pos, y_pos, z_pos = LeapData._get_elbow_offset(hand)
            elif joint_name == 'RightHand':
                x_pos, y_pos, z_pos = LeapData._get_wrist_offset(hand)
            else:
                x_pos, y_pos, z_pos = LeapData._get_finger_offset(joint_name, hand)

            x_rot, y_rot, z_rot = self._calculate_euler_angles(hand, joint_name)

            x_rot *= Leap.RAD_TO_DEG
            y_rot *= Leap.RAD_TO_DEG
            z_rot *= Leap.RAD_TO_DEG

            if firstframe:
                joint_value['offsets'] = [x_pos, y_pos, z_pos]
                x_rot = y_rot = z_rot = 0.0
                print("First Frame detection 2, {}".format(joint_name))

            for channel in joint_value['channels']:
                if channel == 'Xposition':
                    channel_values.append((joint_name, channel, x_pos))
                if channel == 'Yposition':
                    channel_values.append((joint_name, channel, y_pos))
                if channel == 'Zposition':
                    channel_values.append((joint_name, channel, z_pos))
                if channel == 'Xrotation':
                    channel_values.append((joint_name, channel, x_rot))
                if channel == 'Yrotation':
                    channel_values.append((joint_name, channel, y_rot))
                if channel == 'Zrotation':
                    channel_values.append((joint_name, channel, z_rot))
        return channel_values

    def _calculate_euler_angles(self, hand, joint_name):
        initial_hand = self.first_frame.hands[0]

        # special case for root and finger tip
        if joint_name == self._root_name or '4' in joint_name:
            # print("save 0 values, {}".format(joint_name))
            return 0.0, 0.0, 0.0

        parent_initial_basis = self._get_basis(initial_hand, self._skeleton[joint_name]['parent'])
        parent_basis = self._get_basis(hand, self._skeleton[joint_name]['parent'])
        initial_basis = self._get_basis(initial_hand, joint_name)
        basis = self._get_basis(hand, joint_name)

        return rot2eul(
            np.matmul(
                np.matmul(basis, np.transpose(initial_basis)),
                np.transpose(np.matmul(parent_basis, np.transpose(parent_initial_basis)))))

    def _get_basis(self, hand, joint_name):
        if joint_name == self._root_name:
            return np.array([[1, 0, 0],
                             [0, 1, 0],
                             [0, 0, 1]])
        if joint_name == 'RightElbow':
            return LeapData._basismatrix(hand.arm.basis)
        if joint_name == 'RightHand':
            return LeapData._basismatrix(hand.basis)

        # else, return basis of the finger
        finger, bone_number = LeapData._split_key(joint_name)
        fingerlist = hand.fingers.finger_type(LeapData._get_finger_type(finger))
        bone = fingerlist[0].bone(LeapData._get_bone_type(bone_number))
        return LeapData._basismatrix(bone.basis)

    @staticmethod
    def _get_root_offset():
        return 0, 0, 0

    @staticmethod
    def _get_elbow_offset(hand):
        arm = hand.arm
        return arm.elbow_position.x, arm.elbow_position.y, arm.elbow_position.z

    @staticmethod
    def _get_wrist_offset(hand):
        arm = hand.arm
        x_wrist = hand.wrist_position.x - arm.elbow_position.x
        y_wrist = hand.wrist_position.y - arm.elbow_position.y
        z_wrist = hand.wrist_position.z - arm.elbow_position.z

        return x_wrist, y_wrist, z_wrist

    @staticmethod
    def _get_finger_offset(key, hand):
        key, bone_number = LeapData._split_key(key)

        fingerlist = hand.fingers.finger_type(LeapData._get_finger_type(key))

        # vector between wrist and joint metacarpal proximal (length of carpals)
        if bone_number == 1 or ('Thumb' in key and bone_number == 2):
            bone = fingerlist[0].bone(LeapData._get_bone_type(bone_number))
            return \
                bone.prev_joint.x - hand.wrist_position.x, \
                bone.prev_joint.y - hand.wrist_position.y, \
                bone.prev_joint.z - hand.wrist_position.z

        # vector for bones metacarpal, proximal, intermediate, distal
        bone = fingerlist[0].bone(LeapData._get_bone_type(bone_number - 1))
        return \
            bone.next_joint.x - bone.prev_joint.x, \
            bone.next_joint.y - bone.prev_joint.y, \
            bone.next_joint.z - bone.prev_joint.z

    @staticmethod
    def _split_key(key):
        key_split = re.split('(\d)', key)
        key = key_split[0]
        if key_split[-1] == '_End':
            return key, 5
        else:
            return key, int(key_split[1])

    @staticmethod
    def _get_finger_type(key):
        if key == 'RightHandThumb':
            return Leap.Finger.TYPE_THUMB
        if key == 'RightHandIndex':
            return Leap.Finger.TYPE_INDEX
        if key == 'RightHandMiddle':
            return Leap.Finger.TYPE_MIDDLE
        if key == 'RightHandRing':
            return Leap.Finger.TYPE_RING
        if key == 'RightHandPinky':
            return Leap.Finger.TYPE_PINKY
        else:
            raise Exception('Key ({}) did not match'.format(key))

    @staticmethod
    def _get_bone_type(bone_number):
        if bone_number == 4:
            return Leap.Bone.TYPE_DISTAL
        if bone_number == 3:
            return Leap.Bone.TYPE_INTERMEDIATE
        if bone_number == 2:
            return Leap.Bone.TYPE_PROXIMAL
        if bone_number == 1:
            return Leap.Bone.TYPE_METACARPAL
        else:
            raise Exception('bone number ({}) did not match'.format(bone_number))

    @staticmethod
    def _basismatrix(basis):
        return np.array([[basis.x_basis.x, basis.y_basis.x, basis.z_basis.x],
                        [basis.x_basis.y, basis.y_basis.y, basis.z_basis.y],
                        [basis.x_basis.z, basis.y_basis.z, basis.z_basis.z]])

    def _get_channels(self, joint_name, channel_setting):
        if '_End' in joint_name:
            return []

        channels_position = ['Xposition', 'Yposition', 'Zposition']
        channels_rotation = ['Xrotation', 'Yrotation', 'Zrotation']

        order = get_order()  # rotation order, i.e. xyz
        channels_rotation = \
            [channels_rotation[order[0]]] + [channels_rotation[order[1]]] + [channels_rotation[order[2]]]

        if channel_setting == 'position' or joint_name == self._root_name:
            return channels_position + channels_rotation

        return channels_rotation

    def _skeleton_apply_channels(self, channel_setting):
        for joint_name, joint_dict in self._skeleton.items():
            joint_dict['channels'] = self._get_channels(joint_name, channel_setting)

    def _motion2DataFrame(self):
        """Returns all of the channels parsed from the LeapMotion sensor as a pandas DataFrame"""

        time_index = pandas.to_timedelta([f[0] for f in self._motions], unit='s')
        frames = [f[1] for f in self._motions]
        channels = np.asarray([[channel[2] for channel in frame] for frame in frames])
        column_names = ['%s_%s' % (c[0], c[1]) for c in self._motion_channels]

        return pandas.DataFrame(data=channels, index=time_index, columns=column_names)
