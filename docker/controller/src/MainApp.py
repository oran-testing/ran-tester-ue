import logging
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager

from LandingPage import LandingPage
from ProcessesPage import ProcessesPage

from Config import Config

class MainApp(App):
    def build(self):
        self.screen_manager = ScreenManager()

        self.landing = LandingPage(name='landing')
        self.processes = ProcessesPage(name='processes')

        self.screen_manager.add_widget(self.landing)
        self.screen_manager.add_widget(self.processes)

        # Define the button colors
        self.default_color = [1, 1, 1, 1]  # White
        self.highlighted_color = [0, 0.75, 0.25, 1]  # Green

        # Create a layout for the buttons on top
        self.button_layout = BoxLayout(size_hint_y=None, height=50)

        self.button_process_page = Button(text='Processes', on_press=self.switch_to_processes, background_color=self.highlighted_color)

        self.button_layout.add_widget(self.button_process_page)

        main_layout = BoxLayout(orientation='vertical')
        main_layout.add_widget(self.button_layout)
        main_layout.add_widget(self.screen_manager)

        self.button_layout.opacity = 0 
        animationStatus = LandingPage()

        if animationStatus.animation_completed == 1:
                self.button_layout.opacity = 1
        else:
            self.button_layout.opacity = 0  
        Clock.schedule_once(self.load_navigation, 0.25)

        return main_layout

    def load_navigation(self, *args):
        animate = Animation(opacity=1, duration=2)
        animate.start(self.button_layout)

    def switch_to_processes(self, instance):
        self.screen_manager.current = 'processes'
        self.update_button_colors(self.button_process_page)

    def switch_to_attacks(self, instance):
        self.screen_manager.current = 'attacks'

    def switch_to_results(self, instance):
        Clock.schedule_once(lambda dt: self.screen_manager.get_screen('results').init_results())
        self.screen_manager.current = 'results'

    def update_button_colors(self, active_button):
        # Reset all buttons to the default color
        self.button_process_page.background_color = self.default_color

        # Highlight the active button
        active_button.background_color = self.highlighted_color

    def on_stop(self):
        logging.info("App is stopping...")


